from uuid import UUID

from fastapi import APIRouter, Request

from receiptsplit.api.receipts import DB, Actor
from receiptsplit.contracts import BP, Command, ReceiptDTO
from receiptsplit.services import shares as service

router = APIRouter(prefix="/api/v1/receipts")


class ShareCommand(Command):
    share_bp: BP


class RemainingCommand(Command):
    item_id: UUID | None = None


@router.put("/{receipt_id}/items/{item_id}/my-share")
def put_share(
    receipt_id: UUID, item_id: UUID, body: ShareCommand, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    return service.set_share(
        session,
        receipt_id,
        user.id,
        item_id,
        body.share_bp,
        body.expected_version,
        request.app.state.clock.now(),
    )


@router.post("/{receipt_id}/take-remaining")
def take_remaining(
    receipt_id: UUID, body: RemainingCommand, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    return service.take_remaining(
        session,
        receipt_id,
        user.id,
        body.expected_version,
        request.app.state.clock.now(),
        body.item_id,
    )


@router.post("/{receipt_id}/confirm-selection")
def confirm_selection(
    receipt_id: UUID, body: Command, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    return service.confirm_selection(
        session, receipt_id, user.id, body.expected_version, request.app.state.clock.now()
    )
