from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import Field

from receiptsplit.api.receipts import DB, Actor
from receiptsplit.contracts import Command, ReceiptDTO
from receiptsplit.db.receipt_models import Receipt
from receiptsplit.services import settlements as service
from receiptsplit.services.receipts import get_receipt, idempotent

router = APIRouter(prefix="/api/v1/receipts")
Key = Annotated[str | None, Header(alias="Idempotency-Key")]
Amount = Annotated[int, Field(strict=True, ge=1, le=100_000_000)]


class ReportCommand(Command):
    amount_minor: Amount


class ReviewCommand(Command):
    decision: Literal["received", "rejected", "duplicate"]
    amount_minor: Amount | None = None


class CashCommand(Command):
    member_id: UUID
    amount_minor: Amount
    kind: Literal["received", "refund", "correction"]
    reason: str = Field(min_length=1, max_length=500)
    correction_of: UUID | None = None
    direction: Literal[-1, 1] | None = None


class ReturnCommand(Command):
    reason: str = Field(min_length=1, max_length=500)


def mutation(
    receipt_id: UUID,
    body: Command,
    request: Request,
    user: Actor,
    session: DB,
    key: str | None,
    scope: str,
    action: Callable[[Receipt], ReceiptDTO],
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    receipt = get_receipt(session, receipt_id, user.id, now, lock=True)
    return idempotent(
        session,
        user.id,
        f"{receipt_id}:{scope}",
        key,
        body.model_dump(mode="json"),
        now,
        lambda: action(receipt),
    )


@router.post("/{receipt_id}/start-settlement")
def start(
    receipt_id: UUID,
    body: Command,
    request: Request,
    user: Actor,
    session: DB,
    idempotency_key: Key = None,
) -> ReceiptDTO:
    return mutation(
        receipt_id,
        body,
        request,
        user,
        session,
        idempotency_key,
        "start",
        lambda r: service.start(
            session, r, user.id, body.expected_version, request.app.state.clock.now()
        ),
    )


@router.post("/{receipt_id}/payment-reports")
def report(
    receipt_id: UUID,
    body: ReportCommand,
    request: Request,
    user: Actor,
    session: DB,
    idempotency_key: Key = None,
) -> ReceiptDTO:
    return mutation(
        receipt_id,
        body,
        request,
        user,
        session,
        idempotency_key,
        "report",
        lambda r: service.report(
            session,
            r,
            user.id,
            body.expected_version,
            body.amount_minor,
            request.app.state.clock.now(),
        ),
    )


@router.post("/{receipt_id}/payment-reports/{report_id}/review")
def review(
    receipt_id: UUID,
    report_id: UUID,
    body: ReviewCommand,
    request: Request,
    user: Actor,
    session: DB,
    idempotency_key: Key = None,
) -> ReceiptDTO:
    return mutation(
        receipt_id,
        body,
        request,
        user,
        session,
        idempotency_key,
        f"review:{report_id}",
        lambda r: service.review_report(
            session,
            r,
            user.id,
            body.expected_version,
            report_id,
            body.decision,
            body.amount_minor,
            request.app.state.clock.now(),
        ),
    )


@router.post("/{receipt_id}/cash-ledger")
def cash(
    receipt_id: UUID,
    body: CashCommand,
    request: Request,
    user: Actor,
    session: DB,
    idempotency_key: Key = None,
) -> ReceiptDTO:
    return mutation(
        receipt_id,
        body,
        request,
        user,
        session,
        idempotency_key,
        "cash",
        lambda r: service.cash_command(
            session,
            r,
            user.id,
            body.expected_version,
            body.member_id,
            body.amount_minor,
            body.kind,
            body.reason,
            request.app.state.clock.now(),
            body.correction_of,
            body.direction,
        ),
    )


@router.post("/{receipt_id}/return-to-collecting")
def return_to_collecting(
    receipt_id: UUID,
    body: ReturnCommand,
    request: Request,
    user: Actor,
    session: DB,
    idempotency_key: Key = None,
) -> ReceiptDTO:
    return mutation(
        receipt_id,
        body,
        request,
        user,
        session,
        idempotency_key,
        "return",
        lambda r: service.return_to_collecting(
            session, r, user.id, body.expected_version, body.reason, request.app.state.clock.now()
        ),
    )


@router.post("/{receipt_id}/close")
def close(
    receipt_id: UUID,
    body: Command,
    request: Request,
    user: Actor,
    session: DB,
    idempotency_key: Key = None,
) -> ReceiptDTO:
    return mutation(
        receipt_id,
        body,
        request,
        user,
        session,
        idempotency_key,
        "close",
        lambda r: service.close(
            session, r, user.id, body.expected_version, request.app.state.clock.now()
        ),
    )
