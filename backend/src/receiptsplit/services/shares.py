from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from receiptsplit.api.errors import AppError
from receiptsplit.auth.policy import require_creator
from receiptsplit.contracts import ReceiptDTO
from receiptsplit.db.receipt_models import Item, Member, Receipt, Share
from receiptsplit.services.receipts import changed, get_receipt, receipt_dto


def selection_receipt(
    session: Session, receipt_id: UUID, actor_id: UUID, version: int, now: datetime
) -> tuple[Receipt, Member]:
    receipt = get_receipt(session, receipt_id, actor_id, now, lock=True)
    if receipt.version != version:
        raise AppError(
            "version_conflict",
            "Чек изменился. Обновите данные",
            409,
            current_version=receipt.version,
        )
    if receipt.status != "collecting":
        raise AppError("selection_frozen", "Выбор доступен только при распределении", 409)
    member = session.scalars(
        select(Member).where(
            Member.receipt_id == receipt_id, Member.user_id == actor_id, Member.status == "accepted"
        )
    ).one()
    return receipt, member


def set_share(
    session: Session,
    receipt_id: UUID,
    actor_id: UUID,
    item_id: UUID,
    bp: int,
    version: int,
    now: datetime,
) -> ReceiptDTO:
    receipt, member = selection_receipt(session, receipt_id, actor_id, version, now)
    if (
        session.scalar(select(Item.id).where(Item.id == item_id, Item.receipt_id == receipt_id))
        is None
    ):
        raise AppError("not_found", "Позиция недоступна", 404)
    shares = session.scalars(
        select(Share).where(Share.item_id == item_id, Share.receipt_id == receipt_id)
    ).all()
    other_bp = sum(s.share_bp for s in shares if s.member_id != member.id)
    if other_bp + bp > 10000:
        raise AppError(
            "share_overflow",
            "Свободной доли недостаточно",
            409,
            available_bp=10000 - other_bp,
            current_version=receipt.version,
        )
    own = next((s for s in shares if s.member_id == member.id), None)
    if (own.share_bp if own else 0) != bp:
        if bp == 0 and own is not None:
            session.delete(own)
        elif own is not None:
            own.share_bp = bp
        else:
            session.add(
                Share(item_id=item_id, member_id=member.id, receipt_id=receipt_id, share_bp=bp)
            )
        changed(session, receipt, actor_id, now, "share_changed")
    return receipt_dto(session, receipt, actor_id)


def take_remaining(
    session: Session,
    receipt_id: UUID,
    actor_id: UUID,
    version: int,
    now: datetime,
    item_id: UUID | None,
) -> ReceiptDTO:
    receipt, member = selection_receipt(session, receipt_id, actor_id, version, now)
    require_creator(actor_id, receipt.owner_user_id)
    items = session.scalars(select(Item).where(Item.receipt_id == receipt_id)).all()
    if item_id:
        items = [item for item in items if item.id == item_id]
        if not items:
            raise AppError("not_found", "Позиция недоступна", 404)
    any_change = False
    for item in items:
        shares = session.scalars(
            select(Share).where(Share.item_id == item.id, Share.receipt_id == receipt_id)
        ).all()
        remainder = 10000 - sum(s.share_bp for s in shares)
        if remainder:
            own = next((s for s in shares if s.member_id == member.id), None)
            if own is not None:
                own.share_bp += remainder
            else:
                session.add(
                    Share(
                        item_id=item.id,
                        member_id=member.id,
                        receipt_id=receipt_id,
                        share_bp=remainder,
                    )
                )
            any_change = True
    if any_change:
        changed(session, receipt, actor_id, now, "remaining_taken")
    return receipt_dto(session, receipt, actor_id)


def confirm_selection(
    session: Session, receipt_id: UUID, actor_id: UUID, version: int, now: datetime
) -> ReceiptDTO:
    receipt, member = selection_receipt(session, receipt_id, actor_id, version, now)
    if member.confirmed_revision != receipt.financial_revision:
        member.confirmed_revision = receipt.financial_revision
        changed(session, receipt, actor_id, now, "selection_confirmed", financial=False)
    return receipt_dto(session, receipt, actor_id)
