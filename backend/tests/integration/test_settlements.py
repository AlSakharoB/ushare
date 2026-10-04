from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta
from threading import Barrier
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from receiptsplit.api.app import create_app
from receiptsplit.config import Settings
from receiptsplit.db.auth_models import RateBucket, User
from receiptsplit.db.receipt_models import Receipt
from receiptsplit.db.settlement_models import CashLedger, OutboxEvent, Snapshot
from tests.integration.test_auth import TOKEN
from tests.integration.test_receipts import login_test

pytestmark = pytest.mark.integration


class Flow:
    def __init__(self) -> None:
        self.app = create_app(Settings(bot_token=TOKEN))
        self.stack = ExitStack()
        self.clients = {name: self.stack.enter_context(TestClient(self.app)) for name in "abcd"}
        self.headers: dict[str, dict[str, str]] = {}
        self.users: dict[str, str] = {}
        for name, client in self.clients.items():
            self.headers[name], self.users[name] = login_test(client)
        self.url = ""

    def current(self) -> dict[str, Any]:
        return self.clients["a"].get(self.url).json()

    def post(
        self, actor: str, path: str, body: dict[str, Any] | None = None, key: str | None = None
    ) -> Any:
        return self.clients[actor].post(
            self.url + path,
            json={"expected_version": self.current()["version"], **(body or {})},
            headers={**self.headers[actor], "idempotency-key": key or str(uuid4())},
        )

    def initialize(self, items: list[dict[str, Any]], participants: str = "b") -> None:
        receipt = (
            self.clients["a"]
            .post(
                "/api/v1/receipts",
                json={"title": "Расчёт", "items": items},
                headers={**self.headers["a"], "idempotency-key": str(uuid4())},
            )
            .json()
        )
        self.url = "/api/v1/receipts/" + receipt["id"]
        invitation = self.post("a", "/invitations").json()
        for name in participants:
            request = (
                self.clients[name]
                .post(
                    "/api/v1/join-requests",
                    json={"token": invitation["token"]},
                    headers=self.headers[name],
                )
                .json()
            )
            assert (
                self.post(
                    "a", f"/join-requests/{request['id']}/review", {"approve": True}
                ).status_code
                == 200
            )
        assert self.post("a", f"/invitations/{invitation['id']}/revoke").status_code == 200
        assert self.post("a", "/open").status_code == 200

    def choose(self, actor: str, item: int, bp: int) -> dict[str, Any]:
        current = self.current()
        response = self.clients[actor].put(
            self.url + f"/items/{current['items'][item]['id']}/my-share",
            json={"expected_version": current["version"], "share_bp": bp},
            headers=self.headers[actor],
        )
        assert response.status_code == 200, response.text
        return response.json()

    def confirm_and_start(self, participants: str = "b") -> dict[str, Any]:
        for actor in "a" + participants:
            response = self.post(actor, "/confirm-selection")
            assert response.status_code == 200, response.text
        response = self.post("a", "/start-settlement")
        assert response.status_code == 200, response.text
        return response.json()

    def member(self, actor: str) -> str:
        return next(m["id"] for m in self.current()["members"] if m["user_id"] == self.users[actor])


@pytest.fixture
def flow() -> Iterator[Flow]:
    app = create_app()
    with Session(app.state.engine) as session, session.begin():
        session.execute(delete(RateBucket))
    harness = Flow()
    try:
        yield harness
    finally:
        with Session(harness.app.state.engine) as session, session.begin():
            user_ids = [UUID(uid) for uid in harness.users.values()]
            session.execute(delete(Receipt).where(Receipt.owner_user_id.in_(user_ids)))
            session.execute(delete(User).where(User.id.in_(user_ids)))
        harness.stack.close()


def test_e2e01_report_is_not_money_exact_close_and_replay(flow: Flow) -> None:
    flow.initialize(
        [
            {"name": "Пицца", "line_total_minor": 120000},
            {"name": "Напитки", "line_total_minor": 60000},
        ],
        "bc",
    )
    patched = flow.clients["a"].patch(
        flow.url,
        json={
            "expected_version": flow.current()["version"],
            "discount_mode": "percent",
            "discount_value": 1000,
            "tips_mode": "percent",
            "tips_value": 1000,
        },
        headers=flow.headers["a"],
    )
    assert patched.status_code == 200
    flow.choose("a", 0, 5000)
    flow.choose("b", 0, 5000)
    flow.choose("b", 1, 5000)
    flow.choose("c", 1, 5000)
    assert flow.post("a", "/start-settlement").status_code == 409
    settled = flow.confirm_and_start("bc")
    assert settled["calculation"]["total_minor"] == 178200
    assert flow.clients["d"].get(flow.url).status_code == 404
    reported = flow.post("b", "/payment-reports", {"amount_minor": 89100}).json()
    assert reported["cash_balances"][flow.member("b")] == 0
    assert flow.post("b", "/close").status_code == 403
    assert flow.post("a", "/close").status_code == 409
    payment = reported["payment_reports"][-1]
    body = {"expected_version": flow.current()["version"], "decision": "received"}
    key = str(uuid4())
    path = flow.url + f"/payment-reports/{payment['id']}/review"
    headers = {**flow.headers["a"], "idempotency-key": key}
    assert flow.clients["a"].post(path, json=body, headers=headers).status_code == 200
    assert len(flow.clients["a"].post(path, json=body, headers=headers).json()["ledger"]) == 1
    assert flow.post("a", "/close").status_code == 409
    assert (
        flow.post(
            "a",
            "/cash-ledger",
            {
                "member_id": flow.member("c"),
                "amount_minor": 29700,
                "kind": "received",
                "reason": "Получено наличными",
            },
        ).status_code
        == 200
    )
    # A redundant participant report must be explicitly resolved even with exact cash.
    duplicate = flow.post("c", "/payment-reports", {"amount_minor": 29700}).json()[
        "payment_reports"
    ][-1]
    assert flow.post("a", "/close").status_code == 409
    assert (
        flow.post(
            "a", f"/payment-reports/{duplicate['id']}/review", {"decision": "duplicate"}
        ).status_code
        == 200
    )
    body = {"expected_version": flow.current()["version"]}
    headers = {**flow.headers["a"], "idempotency-key": str(uuid4())}
    closed = flow.clients["a"].post(flow.url + "/close", json=body, headers=headers)
    assert closed.status_code == 200, closed.text
    replay = flow.clients["a"].post(flow.url + "/close", json=body, headers=headers).json()
    assert replay["purge_at"] == closed.json()["purge_at"]
    assert datetime.fromisoformat(replay["purge_at"]) - datetime.fromisoformat(
        replay["closed_at"]
    ) == timedelta(days=7)
    assert (
        flow.clients["a"]
        .patch(
            flow.url,
            json={"expected_version": replay["version"], "title": "Изменить"},
            headers=flow.headers["a"],
        )
        .status_code
        == 409
    )
    with Session(flow.app.state.engine) as session:
        assert (
            len(
                session.scalars(
                    select(OutboxEvent).where(OutboxEvent.receipt_id == UUID(replay["id"]))
                ).all()
            )
            >= 6
        )
    with pytest.raises(DBAPIError), Session(flow.app.state.engine) as session, session.begin():
        session.execute(
            update(CashLedger)
            .where(CashLedger.receipt_id == UUID(replay["id"]))
            .values(amount_minor=1)
        )
    with pytest.raises(DBAPIError), Session(flow.app.state.engine) as session, session.begin():
        session.execute(
            update(Snapshot).where(Snapshot.receipt_id == UUID(replay["id"])).values(data={})
        )


@pytest.mark.parametrize(
    "new_due,kind,amount", [(40000, "refund", 10000), (60000, "received", 10000)]
)
def test_e2e04_edit_preserves_money_requires_refund_or_topup(
    flow: Flow, new_due: int, kind: str, amount: int
) -> None:
    flow.initialize([{"name": "Товар", "line_total_minor": 50000}])
    flow.choose("b", 0, 10000)
    settled = flow.confirm_and_start()
    assert (
        flow.post(
            "a",
            "/cash-ledger",
            {
                "member_id": flow.member("b"),
                "amount_minor": 50000,
                "kind": "received",
                "reason": "Получено",
            },
        ).status_code
        == 200
    )
    flow.post("b", "/payment-reports", {"amount_minor": 1})
    returned = flow.post("a", "/return-to-collecting", {"reason": "Цена изменена"})
    assert returned.status_code == 200
    current = returned.json()
    assert current["cash_balances"][flow.member("b")] == 50000
    assert current["payment_reports"][-1]["status"] == "superseded"
    assert all(m["confirmed_revision"] is None for m in current["members"])
    patched = flow.clients["a"].patch(
        flow.url + f"/items/{current['items'][0]['id']}",
        json={"expected_version": current["version"], "name": "Товар", "line_total_minor": new_due},
        headers=flow.headers["a"],
    )
    assert patched.status_code == 200
    assert (
        flow.post(
            "a",
            "/cash-ledger",
            {
                "member_id": flow.member("b"),
                "amount_minor": amount,
                "kind": kind,
                "reason": "Расчёт",
            },
        ).status_code
        == 409
    )
    flow.confirm_and_start()
    assert flow.current()["remaining"][flow.member("b")] == new_due - 50000
    assert flow.post("a", "/close").status_code == 409
    assert (
        flow.clients["a"]
        .request(
            "DELETE",
            flow.url + f"/members/{flow.member('b')}",
            json={"expected_version": flow.current()["version"]},
            headers=flow.headers["a"],
        )
        .status_code
        == 409
    )
    assert (
        flow.post(
            "a",
            "/cash-ledger",
            {
                "member_id": flow.member("b"),
                "amount_minor": amount,
                "kind": kind,
                "reason": "Подтверждён возврат" if kind == "refund" else "Получена доплата",
            },
        ).status_code
        == 200
    )
    with Session(flow.app.state.engine) as session:
        historical = session.get(Snapshot, UUID(settled["snapshot_id"]))
        assert historical is not None and historical.superseded_at is not None
        assert historical.data["calculation"]["total_minor"] == 50000
    assert flow.post("a", "/close").status_code == 200


def test_partial_received_and_compensating_correction(flow: Flow) -> None:
    flow.initialize([{"name": "Товар", "line_total_minor": 50000}])
    flow.choose("b", 0, 10000)
    flow.confirm_and_start()
    reported = flow.post("b", "/payment-reports", {"amount_minor": 50000}).json()
    reviewed = flow.post(
        "a",
        f"/payment-reports/{reported['payment_reports'][-1]['id']}/review",
        {"decision": "received", "amount_minor": 20000},
    ).json()
    assert reviewed["remaining"][flow.member("b")] == 30000
    original = reviewed["ledger"][0]["id"]
    assert (
        flow.post(
            "a",
            "/cash-ledger",
            {
                "member_id": flow.member("b"),
                "amount_minor": 10000,
                "kind": "correction",
                "direction": -1,
                "correction_of": original,
                "reason": "Ошибка ввода, фактически было 100 ₽",
            },
        ).status_code
        == 200
    )
    assert flow.current()["cash_balances"][flow.member("b")] == 10000
    assert (
        flow.post(
            "a",
            "/cash-ledger",
            {
                "member_id": flow.member("b"),
                "amount_minor": 40000,
                "kind": "received",
                "reason": "Остаток получен",
            },
        ).status_code
        == 200
    )
    assert flow.post("a", "/close").status_code == 200


def test_zero_due_and_simultaneous_close_vs_return(flow: Flow) -> None:
    flow.initialize([{"name": "Товар", "line_total_minor": 100}])
    flow.choose("a", 0, 10000)
    current = flow.current()
    assert (
        flow.clients["a"]
        .patch(
            flow.url,
            json={
                "expected_version": current["version"],
                "discount_mode": "percent",
                "discount_value": 10000,
            },
            headers=flow.headers["a"],
        )
        .status_code
        == 200
    )
    settled = flow.confirm_and_start()
    assert all(cost["due_minor"] == 0 for cost in settled["calculation"]["members"].values())
    barrier = Barrier(2)

    def race(path: str) -> Any:
        barrier.wait(timeout=5)
        return flow.clients["a"].post(
            flow.url + path,
            json={
                "expected_version": settled["version"],
                **({"reason": "Правка"} if path == "/return-to-collecting" else {}),
            },
            headers={**flow.headers["a"], "idempotency-key": str(uuid4())},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(race, path) for path in ["/close", "/return-to-collecting"]]
        responses = [f.result(timeout=10) for f in futures]
    assert sorted(r.status_code for r in responses) == [200, 409]
    current = flow.current()
    assert current["status"] in {"closed", "collecting"}
    assert (current["purge_at"] is not None) == (current["status"] == "closed")
