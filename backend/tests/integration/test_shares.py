from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from receiptsplit.api.app import create_app
from receiptsplit.config import Settings
from receiptsplit.db.auth_models import RateBucket, User
from receiptsplit.db.receipt_models import Member, Receipt, Share
from tests.integration.test_auth import TOKEN
from tests.integration.test_receipts import login_test

pytestmark = pytest.mark.integration


def test_simultaneous_share_race_and_confirmation_invalidation() -> None:
    app = create_app(Settings(bot_token=TOKEN))
    with Session(app.state.engine) as session, session.begin():
        session.execute(delete(RateBucket))
    with TestClient(app) as a, TestClient(app) as b, TestClient(app) as c:
        ah, aid = login_test(a)
        bh, bid = login_test(b)
        ch, cid = login_test(c)
        receipt = a.post(
            "/api/v1/receipts",
            json={"title": "Доли", "items": [{"name": "Пицца", "line_total_minor": 100000}]},
            headers={**ah, "idempotency-key": str(uuid4())},
        ).json()
        url = "/api/v1/receipts/" + receipt["id"]
        with Session(app.state.engine) as session, session.begin():
            for uid in [bid, cid]:
                session.add(
                    Member(receipt_id=UUID(receipt["id"]), user_id=UUID(uid), role="participant")
                )
        assert (
            b.put(
                url + f"/items/{receipt['items'][0]['id']}/my-share",
                json={"expected_version": 1, "share_bp": 6000},
                headers=bh,
            ).status_code
            == 409
        )
        receipt = a.post(url + "/open", json={"expected_version": 1}, headers=ah).json()
        share_url = url + f"/items/{receipt['items'][0]['id']}/my-share"
        assert receipt["calculation"]["own_cost_minor"] == 0
        assert receipt["calculation"]["unassigned_minor"] == 100000
        barrier = Barrier(2)

        def choose(client: TestClient, headers: dict[str, str]) -> object:
            barrier.wait(timeout=5)
            return client.put(
                share_url,
                json={"expected_version": receipt["version"], "share_bp": 6000},
                headers=headers,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(choose, b, bh), pool.submit(choose, c, ch)]
            responses = [f.result(timeout=10) for f in futures]
        assert sorted(r.status_code for r in responses) == [200, 409]
        loser, lh = (b, bh) if responses[0].status_code == 409 else (c, ch)
        current = a.get(url).json()
        overflow = loser.put(
            share_url, json={"expected_version": current["version"], "share_bp": 6000}, headers=lh
        )
        assert overflow.status_code == 409 and overflow.json()["details"]["available_bp"] == 4000
        current = loser.put(
            share_url, json={"expected_version": current["version"], "share_bp": 4000}, headers=lh
        ).json()
        assert current["calculation"]["unassigned_minor"] == 0
        confirmed = a.post(
            url + "/confirm-selection", json={"expected_version": current["version"]}, headers=ah
        ).json()
        assert any(
            m["confirmed_revision"] == confirmed["financial_revision"] for m in confirmed["members"]
        )
        current = loser.put(
            share_url, json={"expected_version": confirmed["version"], "share_bp": 1234}, headers=lh
        ).json()
        assert all(m["confirmed_revision"] is None for m in current["members"])
        assert sum(current["items"][0]["shares"].values()) == 7234
        assert (
            loser.put(
                share_url,
                json={
                    "expected_version": current["version"],
                    "share_bp": 1234,
                    "member_id": str(uuid4()),
                },
                headers=lh,
            ).status_code
            == 422
        )
        current = loser.put(
            share_url, json={"expected_version": current["version"], "share_bp": 0}, headers=lh
        ).json()
        with Session(app.state.engine) as session:
            member_id = session.scalar(
                select(Member.id).where(
                    Member.receipt_id == UUID(receipt["id"]),
                    Member.user_id == UUID(bid if loser is b else cid),
                )
            )
            assert session.scalar(select(Share.item_id).where(Share.member_id == member_id)) is None
        assert (
            loser.post(
                url + "/take-remaining", json={"expected_version": current["version"]}, headers=lh
            ).status_code
            == 403
        )
        current = a.post(
            url + "/take-remaining", json={"expected_version": current["version"]}, headers=ah
        ).json()
        assert current["calculation"]["unassigned_minor"] == 0
        assert current["calculation"]["own_cost_minor"] == 40000
        owner_share = next(m["id"] for m in current["members"] if m["user_id"] == aid)
        assert current["items"][0]["shares"][owner_share] == 4000
        current = a.put(
            share_url, json={"expected_version": current["version"], "share_bp": 0}, headers=ah
        ).json()
        winner, wh = (c, ch) if loser is b else (b, bh)
        current = winner.put(
            share_url, json={"expected_version": current["version"], "share_bp": 10000}, headers=wh
        ).json()
        assert current["calculation"]["unassigned_minor"] == 0
        assert current["calculation"]["own_cost_minor"] == 0
        assert (
            loser.put(
                url + f"/items/{uuid4()}/my-share",
                json={"expected_version": current["version"], "share_bp": 1},
                headers=lh,
            ).status_code
            == 404
        )
        with Session(app.state.engine) as session, session.begin():
            session.execute(delete(Receipt).where(Receipt.id == UUID(receipt["id"])))
            session.execute(delete(User).where(User.id.in_([UUID(aid), UUID(bid), UUID(cid)])))
