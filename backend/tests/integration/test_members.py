from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from receiptsplit.api.app import create_app
from receiptsplit.config import Settings
from receiptsplit.db.auth_models import RateBucket, User
from receiptsplit.db.member_models import Invitation, JoinRequest
from receiptsplit.db.receipt_models import Receipt, Share
from tests.integration.test_auth import TOKEN
from tests.integration.test_receipts import login_test

pytestmark = pytest.mark.integration


def test_request_approval_contacts_target_expiry_revoke_and_removal() -> None:
    app = create_app(Settings(bot_token=TOKEN))
    with Session(app.state.engine) as session, session.begin():
        session.execute(delete(RateBucket))
    with TestClient(app) as a, TestClient(app) as b, TestClient(app) as d:
        ah, aid = login_test(a)
        bh, bid = login_test(b)
        dh, did = login_test(d)
        receipt = a.post(
            "/api/v1/receipts",
            json={"title": "Ужин", "items": [{"name": "Пицца", "line_total_minor": 100000}]},
            headers={**ah, "idempotency-key": str(uuid4())},
        ).json()
        url = "/api/v1/receipts/" + receipt["id"]
        assert a.get("/api/v1/contacts").json() == []
        assert (
            a.post(
                url + "/members", json={"expected_version": 1, "user_id": bid}, headers=ah
            ).status_code
            == 422
        )
        invite = a.post(url + "/invitations", json={"expected_version": 1}, headers=ah).json()
        token = {"token": invite["token"]}
        preview = b.post("/api/v1/invitations/resolve", json=token, headers=bh).json()
        assert set(preview) == {"receipt_id", "title", "creator", "targeted"}
        assert b.get(url).status_code == 404
        request = b.post("/api/v1/join-requests", json=token, headers=bh).json()
        assert b.post("/api/v1/join-requests", json=token, headers=bh).json()["id"] == request["id"]
        assert b.get(url).status_code == 404
        other = d.post("/api/v1/join-requests", json=token, headers=dh).json()
        current = a.get(url).json()
        assert len(a.get(url + "/join-requests").json()) == 2
        receipt = a.post(
            url + f"/join-requests/{request['id']}/review",
            json={"expected_version": current["version"], "approve": True},
            headers=ah,
        ).json()
        assert b.get(url).json()["items"] == []
        assert d.get(url).status_code == 404
        assert b.get("/api/v1/receipts").json()["receipts"][0]["id"] == receipt["id"]
        assert a.get("/api/v1/contacts").json()[0]["id"] == bid
        assert d.get("/api/v1/contacts").json() == []
        repeated = a.post(
            url + f"/join-requests/{request['id']}/review",
            json={"expected_version": receipt["version"], "approve": True},
            headers=ah,
        )
        assert len(repeated.json()["members"]) == 2
        receipt = a.post(
            url + f"/invitations/{invite['id']}/revoke",
            json={"expected_version": receipt["version"]},
            headers=ah,
        ).json()
        assert d.post("/api/v1/join-requests", json=token, headers=dh).status_code == 404
        assert a.get(url + "/join-requests").json() == []
        receipt = a.post(
            url + "/open", json={"expected_version": receipt["version"]}, headers=ah
        ).json()
        assert b.get(url).json()["items"][0]["name"] == "Пицца"
        member = next(m for m in receipt["members"] if m["user_id"] == bid)
        with Session(app.state.engine) as session, session.begin():
            session.add(
                Share(
                    item_id=UUID(receipt["items"][0]["id"]),
                    member_id=UUID(member["id"]),
                    receipt_id=UUID(receipt["id"]),
                    share_bp=5000,
                )
            )
        assert (
            a.request(
                "DELETE",
                url + f"/members/{member['id']}",
                json={"expected_version": receipt["version"]},
                headers=ah,
            ).status_code
            == 409
        )
        # A second receipt can use a genuine application contact for targeted invitation.
        second = a.post(
            "/api/v1/receipts",
            json={"title": "Новый"},
            headers={**ah, "idempotency-key": str(uuid4())},
        ).json()
        second_url = "/api/v1/receipts/" + second["id"]
        target_id = a.get("/api/v1/contacts").json()[0]["telegram_id"]
        invitation = a.post(
            second_url + "/invitations",
            json={"expected_version": 1, "target_telegram_id": target_id},
            headers=ah,
        ).json()
        assert (
            d.post(
                "/api/v1/invitations/resolve", json={"token": invitation["token"]}, headers=dh
            ).status_code
            == 403
        )
        accepted = b.post("/api/v1/join-requests", json={"token": invitation["token"]}, headers=bh)
        assert accepted.status_code == 200 and accepted.json()["status"] == "approved"
        assert (
            b.post("/api/v1/join-requests", json={"token": invitation["token"]}, headers=bh).json()[
                "status"
            ]
            == "approved"
        )
        current = a.get(second_url).json()
        assert len(current["members"]) == 2
        target_member = next(m for m in current["members"] if m["user_id"] == bid)
        removed = a.request(
            "DELETE",
            second_url + f"/members/{target_member['id']}",
            json={"expected_version": current["version"]},
            headers=ah,
        )
        assert removed.status_code == 200
        assert b.get(second_url).status_code == 404
        assert (
            b.post(
                "/api/v1/join-requests", json={"token": invitation["token"]}, headers=bh
            ).status_code
            == 404
        )
        current = removed.json()
        expired = a.post(
            second_url + "/invitations", json={"expected_version": current["version"]}, headers=ah
        ).json()
        with Session(app.state.engine) as session, session.begin():
            record = session.get(Invitation, UUID(expired["id"]))
            assert record is not None
            record.expires_at = app.state.clock.now() - timedelta(seconds=1)
            assert record.token_digest != expired["token"]
        assert (
            d.post(
                "/api/v1/join-requests", json={"token": expired["token"]}, headers=dh
            ).status_code
            == 404
        )
        with Session(app.state.engine) as session, session.begin():
            assert (
                session.scalar(select(JoinRequest.id).where(JoinRequest.id == UUID(other["id"])))
                is not None
            )
            session.execute(
                delete(Receipt).where(Receipt.id.in_([UUID(receipt["id"]), UUID(second["id"])]))
            )
            session.execute(delete(User).where(User.id.in_([UUID(aid), UUID(bid), UUID(did)])))
