import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from receiptsplit.api.app import create_app
from receiptsplit.config import Settings
from receiptsplit.db.auth_models import RateBucket, User, UserSession

pytestmark = pytest.mark.integration
TOKEN = "12345:integration-test-token"


def signed_data(user_id: int, now: datetime, **extra: str) -> str:
    fields = {
        "auth_date": str(int(now.timestamp())),
        "user": json.dumps({"id": user_id, "first_name": "Тест"}),
        **extra,
    }
    secret = hmac.digest(b"WebAppData", TOKEN.encode(), "sha256")
    fields["hash"] = hmac.new(
        secret, "\n".join(f"{key}={fields[key]}" for key in sorted(fields)).encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(fields)


class FrozenClock:
    def __init__(self, now: datetime) -> None:
        self.value = now

    def now(self) -> datetime:
        return self.value


def test_sessions_csrf_origin_expiry_logout_and_db_digest() -> None:
    app = create_app(Settings(bot_token=TOKEN))
    clock = FrozenClock(datetime.now(UTC))
    app.state.clock = clock
    user_id = uuid4().int % (2**50)
    with Session(app.state.engine) as session, session.begin():
        session.execute(delete(RateBucket))
    with TestClient(app) as client:
        assert client.get("/api/v1/me").status_code == 401
        assert (
            client.post(
                "/api/v1/auth/telegram", json={"init_data": signed_data(user_id, clock.now())}
            ).status_code
            == 403
        )
        response = client.post(
            "/api/v1/auth/telegram",
            json={"init_data": signed_data(user_id, clock.now())},
            headers={"origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        csrf = response.json()["csrf_token"]
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=lax" in response.headers["set-cookie"]
        assert client.get("/api/v1/me").json()["telegram_id"] == user_id
        with Session(app.state.engine) as session:
            user = session.scalars(select(User).where(User.telegram_id == user_id)).one()
            auth_session = session.scalars(
                select(UserSession).where(UserSession.user_id == user.id)
            ).one()
            assert auth_session.token_digest != client.cookies["receiptsplit_session"]
            assert auth_session.csrf_digest != csrf
        assert (
            client.post(
                "/api/v1/auth/logout", headers={"origin": "http://localhost:5173"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/auth/logout",
                headers={"origin": "https://foreign.invalid", "x-csrf-token": csrf},
            ).status_code
            == 403
        )
        clock.value += timedelta(hours=12)
        assert client.get("/api/v1/me").status_code == 401
        clock.value -= timedelta(hours=12)
        assert (
            client.post(
                "/api/v1/auth/logout",
                headers={"origin": "http://localhost:5173", "x-csrf-token": csrf},
            ).status_code
            == 204
        )
        assert client.get("/api/v1/me").status_code == 401
        # Client identity is never accepted alongside signed initData.
        assert (
            client.post(
                "/api/v1/auth/telegram",
                json={"init_data": signed_data(user_id, clock.now()), "user_id": str(uuid4())},
                headers={"origin": "http://localhost:5173"},
            ).status_code
            == 422
        )
        with Session(app.state.engine) as session, session.begin():
            session.execute(delete(User).where(User.telegram_id == user_id))


def test_missing_user_signed_invalid_and_dev_isolation() -> None:
    app = create_app(Settings(bot_token=TOKEN))
    with Session(app.state.engine) as session, session.begin():
        session.execute(delete(RateBucket))
    with TestClient(app) as client:
        headers = {"origin": "http://localhost:5173"}
        assert (
            client.post(
                "/api/v1/auth/telegram",
                json={"init_data": signed_data(1, datetime.now(UTC), user="{}")},
                headers=headers,
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/auth/dev", json={"telegram_id": 1, "first_name": "Test"}, headers=headers
            ).status_code
            == 404
        )
        for _ in range(20):
            client.post("/api/v1/auth/telegram", json={"init_data": "hash=bad"}, headers=headers)
        assert (
            client.post(
                "/api/v1/auth/telegram",
                json={"init_data": signed_data(1, datetime.now(UTC))},
                headers=headers,
            ).status_code
            == 429
        )
