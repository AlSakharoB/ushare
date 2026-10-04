from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from receiptsplit.api.app import create_app
from receiptsplit.config import Settings
from receiptsplit.db.auth_models import RateBucket, User
from receiptsplit.db.receipt_models import Member, Receipt, Share
from tests.integration.test_auth import TOKEN, signed_data

pytestmark = pytest.mark.integration


def login_test(client: TestClient) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": signed_data(uuid4().int % (2**50), datetime.now(UTC))},
        headers={"origin": "http://localhost:5173"},
    )
    assert response.status_code == 200, response.text
    return {
        "origin": "http://localhost:5173",
        "x-csrf-token": response.json()["csrf_token"],
    }, response.json()["user"]["id"]


def test_manual_crud_acl_versions_idempotency_rollback_and_cascade() -> None:
    app = create_app(Settings(bot_token=TOKEN))
    with Session(app.state.engine) as session, session.begin():
        session.execute(delete(RateBucket))
    with TestClient(app) as owner, TestClient(app) as stranger, TestClient(app) as participant:
        headers, owner_id = login_test(owner)
        stranger_headers, stranger_id = login_test(stranger)
        participant_headers, participant_id = login_test(participant)
        payload = {"title": "Ужин", "items": [{"name": "Пицца", "line_total_minor": 100000}]}
        key_headers = {**headers, "idempotency-key": str(uuid4())}
        response = owner.post("/api/v1/receipts", json=payload, headers=key_headers)
        assert response.status_code == 201, response.text
        receipt = response.json()
        rid = receipt["id"]
        url = f"/api/v1/receipts/{rid}"
        assert owner.post("/api/v1/receipts", json=payload, headers=key_headers).json()["id"] == rid
        assert (
            owner.post(
                "/api/v1/receipts", json={**payload, "title": "Иное"}, headers=key_headers
            ).status_code
            == 409
        )
        assert stranger.get(url).status_code == 404
        assert stranger.get("/api/v1/receipts").json()["receipts"] == []
        assert (
            stranger.patch(
                url, json={"expected_version": 1, "title": "Hack"}, headers=stranger_headers
            ).status_code
            == 404
        )
        with Session(app.state.engine) as session, session.begin():
            session.add(
                Member(receipt_id=UUID(rid), user_id=UUID(participant_id), role="participant")
            )
        draft = participant.get(url).json()
        assert draft["items"] == [] and draft["calculation"] is None
        assert len(draft["members"]) == 1
        assert (
            participant.patch(
                url, json={"expected_version": 1, "title": "Hack"}, headers=participant_headers
            ).status_code
            == 403
        )
        response = owner.patch(
            url,
            json={
                "expected_version": 1,
                "discount_mode": "percent",
                "discount_value": 1000,
                "tips_mode": "percent",
                "tips_value": 1000,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["calculation"]["total_minor"] == 99000
        assert (
            owner.patch(
                url, json={"expected_version": 1, "title": "Stale"}, headers=headers
            ).status_code
            == 409
        )
        current = response.json()
        assert (
            owner.patch(
                url,
                json={"expected_version": current["version"], "discount_value": 10001},
                headers=headers,
            ).status_code
            == 422
        )
        assert owner.get(url).json()["version"] == current["version"]
        response = owner.post(
            url + "/open", json={"expected_version": current["version"]}, headers=headers
        )
        assert response.status_code == 200, response.text
        assert participant.get(url).json()["items"][0]["name"] == "Пицца"
        current = response.json()
        response = owner.post(
            url + "/items",
            json={
                "expected_version": current["version"],
                "name": "Вода",
                "quantity": "2",
                "unit_price_minor": 300,
                "line_total_minor": 600,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        current = response.json()
        item_id = current["items"][-1]["id"]
        with Session(app.state.engine) as session, session.begin():
            member = session.scalars(
                select(Member).where(
                    Member.receipt_id == UUID(rid), Member.user_id == UUID(participant_id)
                )
            ).one()
            member_id = member.id
            session.add(
                Share(
                    item_id=UUID(item_id), member_id=member.id, receipt_id=UUID(rid), share_bp=5000
                )
            )
        response = owner.request(
            "DELETE",
            url + f"/items/{item_id}",
            json={"expected_version": current["version"]},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        with Session(app.state.engine) as session:
            assert session.scalar(select(Share).where(Share.item_id == UUID(item_id))) is None
        current = response.json()
        bad = owner.post(
            url + "/items",
            json={
                "expected_version": current["version"],
                "name": "Вода",
                "quantity": "2",
                "unit_price_minor": 300,
                "line_total_minor": 601,
            },
            headers=headers,
        )
        assert bad.status_code == 422
        assert owner.get(url).json()["version"] == current["version"]
        # Another receipt's item cannot be attached by URL.
        other = owner.post(
            "/api/v1/receipts", json=payload, headers={**headers, "idempotency-key": str(uuid4())}
        ).json()
        assert (
            owner.patch(
                url + f"/items/{other['items'][0]['id']}",
                json={
                    "expected_version": current["version"],
                    "name": "hack",
                    "line_total_minor": 100,
                },
                headers=headers,
            ).status_code
            == 404
        )
        with pytest.raises(IntegrityError), Session(app.state.engine) as session, session.begin():
            session.add(
                Share(
                    item_id=UUID(other["items"][0]["id"]),
                    member_id=member_id,
                    receipt_id=UUID(rid),
                    share_bp=1,
                )
            )
            session.flush()
        assert owner.get("/api/v1/receipts?limit=1").json()["next_cursor"] is not None
        with Session(app.state.engine) as session, session.begin():
            session.execute(delete(Receipt).where(Receipt.id.in_([UUID(rid), UUID(other["id"])])))
            session.execute(
                delete(User).where(
                    User.id.in_([UUID(owner_id), UUID(stranger_id), UUID(participant_id)])
                )
            )


def test_printed_total_review_and_manual_partial_discount() -> None:
    app = create_app(Settings(bot_token=TOKEN))
    with Session(app.state.engine) as session, session.begin():
        session.execute(delete(RateBucket))
    with TestClient(app) as client:
        headers, user_id = login_test(client)
        response = client.post(
            "/api/v1/receipts",
            json={
                "title": "Тест",
                "items": [
                    {
                        "name": "Скидка магазина",
                        "quantity": "2",
                        "unit_price_minor": 100,
                        "line_total_minor": 180,
                        "mismatch_reason": "Скидка в строке",
                    }
                ],
            },
            headers={**headers, "idempotency-key": str(uuid4())},
        )
        assert response.status_code == 201
        url = "/api/v1/receipts/" + response.json()["id"]
        updated = client.patch(
            url, json={"expected_version": 1, "printed_total_minor": 200}, headers=headers
        ).json()
        assert (
            client.post(
                url + "/open", json={"expected_version": updated["version"]}, headers=headers
            ).status_code
            == 422
        )
        updated = client.patch(
            url,
            json={
                "expected_version": updated["version"],
                "printed_total_reason": "Печатный итог неверен",
            },
            headers=headers,
        ).json()
        assert (
            client.post(
                url + "/open", json={"expected_version": updated["version"]}, headers=headers
            ).status_code
            == 200
        )
        with Session(app.state.engine) as session, session.begin():
            session.execute(delete(Receipt).where(Receipt.id == UUID(updated["id"])))
            session.execute(delete(User).where(User.id == UUID(user_id)))
