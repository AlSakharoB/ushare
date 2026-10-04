import json
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from receiptsplit.api.errors import AppError
from receiptsplit.auth.policy import require_accepted, require_creator
from receiptsplit.auth.service import digest
from receiptsplit.contracts import (
    CalculationDTO,
    CreateReceipt,
    ItemDTO,
    ItemInput,
    LedgerDTO,
    MemberDTO,
    PatchReceipt,
    PaymentReportDTO,
    ReceiptDTO,
)
from receiptsplit.db.auth_models import User
from receiptsplit.db.receipt_models import AuditEvent, IdempotencyKey, Item, Member, Receipt, Share
from receiptsplit.db.settlement_models import CashLedger, PaymentReport, Snapshot
from receiptsplit.domain.money import Calculation, Discount, Line, MoneyError, Tips, calculate
from receiptsplit.domain.states import ReceiptStatus, Revision, StateError, validate_transition


def get_receipt(
    session: Session, receipt_id: UUID, actor_id: UUID, now: datetime, *, lock: bool = False
) -> Receipt:
    query = select(Receipt).where(Receipt.id == receipt_id)
    if lock:
        query = query.with_for_update()
    else:
        query = query.with_for_update(read=True)
    receipt = session.scalars(query).one_or_none()
    if receipt is None or (receipt.purge_at is not None and receipt.purge_at <= now):
        raise AppError("not_found", "Чек недоступен", 404)
    member = session.scalar(
        select(Member.id).where(
            Member.receipt_id == receipt_id, Member.user_id == actor_id, Member.status == "accepted"
        )
    )
    require_accepted(member is not None)
    return receipt


def editable(receipt: Receipt, actor_id: UUID, expected_version: int) -> None:
    require_creator(actor_id, receipt.owner_user_id)
    if receipt.version != expected_version:
        raise AppError(
            "version_conflict",
            "Чек изменился. Обновите данные",
            409,
            current_version=receipt.version,
        )
    if receipt.status not in {"draft", "collecting"}:
        raise AppError("receipt_frozen", "Верните чек к распределению перед правкой", 409)


def changed(
    session: Session,
    receipt: Receipt,
    actor_id: UUID,
    now: datetime,
    event: str,
    *,
    financial: bool = True,
) -> None:
    revision = Revision(receipt.version, receipt.financial_revision).change(financial)
    receipt.version, receipt.financial_revision = revision.version, revision.financial
    if financial:
        receipt.printed_total_reason = None
        session.execute(
            update(Member).where(Member.receipt_id == receipt.id).values(confirmed_revision=None)
        )
    session.add(
        AuditEvent(
            receipt_id=receipt.id,
            actor_id=actor_id,
            event=event,
            revision=receipt.financial_revision,
            created_at=now,
        )
    )
    session.flush()


def calculation(session: Session, receipt: Receipt) -> Calculation:
    items = session.scalars(
        select(Item).where(Item.receipt_id == receipt.id).order_by(Item.id)
    ).all()
    members = session.scalars(
        select(Member).where(Member.receipt_id == receipt.id, Member.status == "accepted")
    ).all()
    shares = session.scalars(select(Share).where(Share.receipt_id == receipt.id)).all()
    owner = next(m for m in members if m.user_id == receipt.owner_user_id)
    lines = [
        Line(
            str(item.id),
            item.line_total_minor,
            {str(s.member_id): s.share_bp for s in shares if s.item_id == item.id},
        )
        for item in items
    ]
    try:
        return calculate(
            lines,
            [str(m.id) for m in members],
            str(owner.id),
            Discount(
                cast(Literal["fixed", "percent"], receipt.discount_mode), receipt.discount_value
            ),
            Tips(cast(Literal["fixed", "percent"], receipt.tips_mode), receipt.tips_value),
        )
    except MoneyError as exc:
        raise AppError("invalid_calculation", str(exc)) from exc


def receipt_dto(session: Session, receipt: Receipt, actor_id: UUID) -> ReceiptDTO:
    financial_visible = receipt.status != "draft" or actor_id == receipt.owner_user_id
    items = (
        session.scalars(
            select(Item).where(Item.receipt_id == receipt.id).order_by(Item.sort_order, Item.id)
        ).all()
        if financial_visible
        else []
    )
    shares = (
        session.scalars(select(Share).where(Share.receipt_id == receipt.id)).all()
        if financial_visible
        else []
    )
    member_query = (
        select(Member, User)
        .join(User, Member.user_id == User.id)
        .where(Member.receipt_id == receipt.id)
    )
    if not financial_visible:
        member_query = member_query.where(Member.user_id == actor_id)
    members = session.execute(member_query.order_by(Member.id)).all()
    dto = ReceiptDTO(
        id=receipt.id,
        title=receipt.title,
        currency=receipt.currency,
        owner_user_id=receipt.owner_user_id,
        status=receipt.status,
        version=receipt.version,
        financial_revision=receipt.financial_revision,
        created_at=receipt.created_at,
        closed_at=receipt.closed_at,
        purge_at=receipt.purge_at,
        discount_mode=receipt.discount_mode if financial_visible else None,
        discount_value=receipt.discount_value if financial_visible else None,
        tips_mode=receipt.tips_mode if financial_visible else None,
        tips_value=receipt.tips_value if financial_visible else None,
        printed_total_minor=receipt.printed_total_minor if financial_visible else None,
        printed_total_reason=receipt.printed_total_reason if financial_visible else None,
        items=[
            ItemDTO(
                id=i.id,
                name=i.name,
                quantity=str(i.quantity),
                unit_price_minor=i.unit_price_minor,
                line_total_minor=i.line_total_minor,
                origin=i.origin,
                reviewed=i.reviewed,
                shares={str(s.member_id): s.share_bp for s in shares if s.item_id == i.id},
            )
            for i in items
        ],
        members=[
            MemberDTO(
                id=m.id,
                user_id=m.user_id,
                display_name=u.display_name,
                role=m.role,
                status=m.status,
                confirmed_revision=m.confirmed_revision,
            )
            for m, u in members
        ],
        calculation=CalculationDTO.model_validate(calculation(session, receipt).to_dict())
        if financial_visible
        else None,
    )
    if financial_visible:
        snapshot = session.scalar(
            select(Snapshot)
            .where(Snapshot.receipt_id == receipt.id, Snapshot.superseded_at.is_(None))
            .order_by(Snapshot.created_at.desc())
        )
        if snapshot is not None and receipt.status in {"settling", "closed"}:
            dto.snapshot_id = snapshot.id
            dto.calculation = CalculationDTO.model_validate(snapshot.data["calculation"])
        ledger = session.scalars(
            select(CashLedger)
            .where(CashLedger.receipt_id == receipt.id)
            .order_by(CashLedger.created_at, CashLedger.id)
        ).all()
        dto.ledger = [LedgerDTO.model_validate(entry) for entry in ledger]
        dto.cash_balances = {
            str(m.id): sum(
                entry.direction * entry.amount_minor for entry in ledger if entry.member_id == m.id
            )
            for m, _ in members
        }
        if dto.calculation is not None:
            dto.remaining = {
                key: cost.due_minor - dto.cash_balances.get(key, 0)
                for key, cost in dto.calculation.members.items()
            }
        dto.payment_reports = [
            PaymentReportDTO.model_validate(payment)
            for payment in session.scalars(
                select(PaymentReport)
                .where(PaymentReport.receipt_id == receipt.id)
                .order_by(PaymentReport.created_at, PaymentReport.id)
            )
        ]
    return dto


def idempotent(
    session: Session,
    actor_id: UUID,
    scope: str,
    key: str | None,
    payload: dict[str, Any],
    now: datetime,
    action: Callable[[], ReceiptDTO],
) -> ReceiptDTO:
    if key is None or not 8 <= len(key) <= 128:
        raise AppError(
            "idempotency_key_required", "Требуется Idempotency-Key длиной 8–128 символов"
        )
    key_hash = digest(key)
    body_hash = digest(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    lock_number = int.from_bytes(
        bytes.fromhex(digest(str(actor_id) + scope + key_hash))[:8], "big", signed=True
    )
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_number})
    previous = session.get(IdempotencyKey, (actor_id, scope, key_hash))
    if previous and previous.expires_at <= now:
        session.delete(previous)
        session.flush()
        previous = None
    if previous:
        if previous.request_digest != body_hash:
            raise AppError(
                "idempotency_conflict", "Этот ключ уже использован с другими данными", 409
            )
        if previous.receipt_id:
            get_receipt(session, previous.receipt_id, actor_id, now)
        return ReceiptDTO.model_validate(previous.result)
    result = action()
    session.add(
        IdempotencyKey(
            actor_id=actor_id,
            scope=scope,
            key_digest=key_hash,
            request_digest=body_hash,
            result=result.model_dump(mode="json"),
            receipt_id=result.id,
            expires_at=now + timedelta(hours=24),
        )
    )
    session.flush()
    return result


def validate_item(body: ItemInput) -> None:
    if (
        body.unit_price_minor is not None
        and Decimal(body.quantity) * body.unit_price_minor != body.line_total_minor
        and not (body.mismatch_reason or "").strip()
    ):
        raise AppError(
            "line_total_mismatch", "Подтвердите причину различия количества, цены и итога"
        )


def create_receipt(
    session: Session, actor_id: UUID, body: CreateReceipt, now: datetime
) -> ReceiptDTO:
    if not body.title.strip():
        raise AppError("invalid_title", "Введите название")
    receipt = Receipt(owner_user_id=actor_id, title=body.title.strip(), created_at=now)
    session.add(receipt)
    session.flush()
    session.add(Member(receipt_id=receipt.id, user_id=actor_id, role="creator"))
    for order, item in enumerate(body.items):
        validate_item(item)
        session.add(
            Item(
                receipt_id=receipt.id,
                sort_order=order,
                name=item.name,
                quantity=Decimal(item.quantity),
                unit_price_minor=item.unit_price_minor,
                line_total_minor=item.line_total_minor,
                mismatch_reason=item.mismatch_reason,
            )
        )
    session.flush()
    calculation(session, receipt)
    session.add(
        AuditEvent(
            receipt_id=receipt.id,
            actor_id=actor_id,
            event="receipt_created",
            revision=1,
            created_at=now,
        )
    )
    return receipt_dto(session, receipt, actor_id)


def patch_receipt(
    session: Session, receipt: Receipt, actor_id: UUID, body: PatchReceipt, now: datetime
) -> ReceiptDTO:
    editable(receipt, actor_id, body.expected_version)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_version"})
    financial = bool(set(fields) & {"discount_mode", "discount_value", "tips_mode", "tips_value"})
    reason = fields.pop("printed_total_reason", None)
    for key, value in fields.items():
        if value is None and key != "printed_total_minor":
            raise AppError("invalid_value", "Поле не может быть пустым")
        if key == "title" and not str(value).strip():
            raise AppError("invalid_title", "Введите название")
        setattr(receipt, key, value)
    with session.no_autoflush:
        calculation(session, receipt)
    changed(session, receipt, actor_id, now, "receipt_updated", financial=financial)
    if reason is not None:
        receipt.printed_total_reason = reason.strip() or None
    calculation(session, receipt)
    return receipt_dto(session, receipt, actor_id)


def save_item(
    session: Session,
    receipt: Receipt,
    actor_id: UUID,
    body: ItemInput,
    expected: int,
    now: datetime,
    item_id: UUID | None = None,
) -> ReceiptDTO:
    editable(receipt, actor_id, expected)
    validate_item(body)
    item = (
        session.scalar(select(Item).where(Item.id == item_id, Item.receipt_id == receipt.id))
        if item_id
        else None
    )
    if item_id and item is None:
        raise AppError("not_found", "Позиция недоступна", 404)
    if item is None:
        count = len(session.scalars(select(Item.id).where(Item.receipt_id == receipt.id)).all())
        if count >= 500:
            raise AppError("item_limit", "Максимум 500 позиций")
        item = Item(receipt_id=receipt.id, sort_order=count)
        session.add(item)
    for key, value in body.model_dump().items():
        setattr(item, key, Decimal(value) if key == "quantity" else value)
    item.reviewed = True
    changed(session, receipt, actor_id, now, "item_saved")
    calculation(session, receipt)
    return receipt_dto(session, receipt, actor_id)


def delete_item(
    session: Session, receipt: Receipt, actor_id: UUID, item_id: UUID, expected: int, now: datetime
) -> ReceiptDTO:
    editable(receipt, actor_id, expected)
    item = session.scalar(select(Item).where(Item.id == item_id, Item.receipt_id == receipt.id))
    if item is None:
        raise AppError("not_found", "Позиция недоступна", 404)
    session.delete(item)
    changed(session, receipt, actor_id, now, "item_deleted")
    calculation(session, receipt)
    return receipt_dto(session, receipt, actor_id)


def open_receipt(
    session: Session, receipt: Receipt, actor_id: UUID, expected: int, now: datetime
) -> ReceiptDTO:
    editable(receipt, actor_id, expected)
    items = session.scalars(select(Item).where(Item.receipt_id == receipt.id)).all()
    result = calculation(session, receipt)
    if (
        receipt.printed_total_minor is not None
        and receipt.printed_total_minor != result.subtotal_minor
        and not receipt.printed_total_reason
    ):
        raise AppError("printed_total_mismatch", "Подтвердите причину расхождения печатного итога")
    try:
        validate_transition(
            ReceiptStatus(receipt.status),
            ReceiptStatus.COLLECTING,
            creator=True,
            positive_items=bool(items),
            reviewed=all(i.reviewed for i in items),
        )
    except StateError as exc:
        raise AppError("invalid_transition", str(exc), 409) from exc
    receipt.status = "collecting"
    changed(session, receipt, actor_id, now, "receipt_opened", financial=False)
    return receipt_dto(session, receipt, actor_id)
