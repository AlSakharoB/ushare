from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from receiptsplit.api.dependencies import actor, db_session
from receiptsplit.contracts import (
    Command,
    CreateReceipt,
    ItemCommand,
    ItemInput,
    PatchReceipt,
    ReceiptDTO,
    ReceiptPage,
)
from receiptsplit.db.auth_models import User
from receiptsplit.db.receipt_models import Member, Receipt
from receiptsplit.services import receipts as service

router = APIRouter(prefix="/api/v1/receipts")
Actor = Annotated[User, Depends(actor)]
DB = Annotated[Session, Depends(db_session)]


@router.post("", status_code=201)
def create(
    body: CreateReceipt,
    request: Request,
    user: Actor,
    session: DB,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    return service.idempotent(
        session,
        user.id,
        "receipts:create",
        idempotency_key,
        body.model_dump(mode="json"),
        now,
        lambda: service.create_receipt(session, user.id, body, now),
    )


@router.get("")
def list_receipts(
    request: Request,
    user: Actor,
    session: DB,
    cursor: UUID | None = None,
    status: Literal["draft", "collecting", "settling", "closed"] | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ReceiptPage:
    now = request.app.state.clock.now()
    query = (
        select(Receipt)
        .join(Member, Member.receipt_id == Receipt.id)
        .where(
            Member.user_id == user.id,
            Member.status == "accepted",
            (Receipt.purge_at.is_(None) | (Receipt.purge_at > now)),
        )
    )
    if cursor:
        query = query.where(Receipt.id > cursor)
    if status:
        query = query.where(Receipt.status == status)
    rows = session.scalars(
        query.order_by(Receipt.id).limit(limit + 1).with_for_update(read=True, of=Receipt)
    ).all()
    return ReceiptPage(
        receipts=[service.receipt_dto(session, receipt, user.id) for receipt in rows[:limit]],
        next_cursor=rows[limit - 1].id if len(rows) > limit else None,
    )


@router.get("/{receipt_id}")
def read(receipt_id: UUID, request: Request, user: Actor, session: DB) -> ReceiptDTO:
    return service.receipt_dto(
        session,
        service.get_receipt(session, receipt_id, user.id, request.app.state.clock.now()),
        user.id,
    )


@router.patch("/{receipt_id}")
def patch(
    receipt_id: UUID, body: PatchReceipt, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    return service.patch_receipt(
        session,
        service.get_receipt(session, receipt_id, user.id, now, lock=True),
        user.id,
        body,
        now,
    )


@router.post("/{receipt_id}/items")
def create_item(
    receipt_id: UUID, body: ItemCommand, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    return service.save_item(
        session,
        service.get_receipt(session, receipt_id, user.id, now, lock=True),
        user.id,
        ItemInput.model_validate(body.model_dump(exclude={"expected_version"})),
        body.expected_version,
        now,
    )


@router.patch("/{receipt_id}/items/{item_id}")
def patch_item(
    receipt_id: UUID, item_id: UUID, body: ItemCommand, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    return service.save_item(
        session,
        service.get_receipt(session, receipt_id, user.id, now, lock=True),
        user.id,
        ItemInput.model_validate(body.model_dump(exclude={"expected_version"})),
        body.expected_version,
        now,
        item_id,
    )


@router.delete("/{receipt_id}/items/{item_id}")
def remove_item(
    receipt_id: UUID, item_id: UUID, body: Command, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    return service.delete_item(
        session,
        service.get_receipt(session, receipt_id, user.id, now, lock=True),
        user.id,
        item_id,
        body.expected_version,
        now,
    )


@router.get("/{receipt_id}/calculation")
def receipt_calculation(receipt_id: UUID, request: Request, user: Actor, session: DB) -> ReceiptDTO:
    return read(receipt_id, request, user, session)


@router.post("/{receipt_id}/open")
def open_for_selection(
    receipt_id: UUID, body: Command, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    return service.open_receipt(
        session,
        service.get_receipt(session, receipt_id, user.id, now, lock=True),
        user.id,
        body.expected_version,
        now,
    )
