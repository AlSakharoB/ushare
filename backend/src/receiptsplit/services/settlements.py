from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from receiptsplit.api.errors import AppError
from receiptsplit.auth.policy import require_creator
from receiptsplit.contracts import ReceiptDTO
from receiptsplit.db.member_models import Invitation, JoinRequest
from receiptsplit.db.receipt_models import Item, Member, Receipt, Share
from receiptsplit.db.settlement_models import CashLedger, OutboxEvent, PaymentReport, Snapshot
from receiptsplit.domain.states import (
    ReceiptStatus,
    StateError,
    validate_close,
    validate_transition,
)
from receiptsplit.services.receipts import changed, receipt_dto


def check_version(receipt: Receipt, version: int) -> None:
    if receipt.version != version:
        raise AppError(
            "version_conflict",
            "Чек изменился. Обновите данные",
            409,
            current_version=receipt.version,
        )


def current_snapshot(session: Session, receipt: Receipt) -> Snapshot:
    snapshot = session.scalar(
        select(Snapshot)
        .where(Snapshot.receipt_id == receipt.id, Snapshot.superseded_at.is_(None))
        .order_by(Snapshot.created_at.desc())
    )
    if snapshot is None or snapshot.revision != receipt.financial_revision:
        raise AppError("snapshot_outdated", "Нет актуального расчёта для перевода", 409)
    return snapshot


def emit(
    session: Session, receipt: Receipt, event: str, now: datetime, snapshot_id: UUID | None = None
) -> None:
    session.add(
        OutboxEvent(
            receipt_id=receipt.id,
            event=event,
            payload={
                "revision": receipt.financial_revision,
                "snapshot_id": str(snapshot_id) if snapshot_id else None,
            },
            available_at=now,
        )
    )


def start(
    session: Session, receipt: Receipt, actor_id: UUID, version: int, now: datetime
) -> ReceiptDTO:
    require_creator(actor_id, receipt.owner_user_id)
    check_version(receipt, version)
    items = session.scalars(select(Item).where(Item.receipt_id == receipt.id)).all()
    shares = session.scalars(select(Share).where(Share.receipt_id == receipt.id)).all()
    members = session.scalars(
        select(Member).where(Member.receipt_id == receipt.id, Member.status == "accepted")
    ).all()
    pending = (
        session.scalar(
            select(JoinRequest.id)
            .where(JoinRequest.receipt_id == receipt.id, JoinRequest.status == "pending")
            .limit(1)
        )
        is not None
    )
    pending |= (
        session.scalar(
            select(Invitation.id)
            .where(
                Invitation.receipt_id == receipt.id,
                Invitation.revoked_at.is_(None),
                Invitation.consumed_at.is_(None),
                Invitation.expires_at > now,
            )
            .limit(1)
        )
        is not None
    )
    try:
        validate_transition(
            ReceiptStatus(receipt.status),
            ReceiptStatus.SETTLING,
            creator=True,
            positive_items=bool(items),
            reviewed=all(i.reviewed for i in items),
            fully_assigned=all(
                sum(s.share_bp for s in shares if s.item_id == i.id) == 10000 for i in items
            ),
            all_confirmed=all(m.confirmed_revision == receipt.financial_revision for m in members),
            pending_invitations=pending,
        )
    except StateError as exc:
        raise AppError("settlement_not_ready", str(exc), 409) from exc
    dto = receipt_dto(session, receipt, actor_id)
    if (
        receipt.printed_total_minor is not None
        and dto.calculation is not None
        and receipt.printed_total_minor != dto.calculation.subtotal_minor
        and not receipt.printed_total_reason
    ):
        raise AppError("printed_total_mismatch", "Подтвердите расхождение печатного итога")
    snapshot = Snapshot(
        receipt_id=receipt.id,
        revision=receipt.financial_revision,
        data=dto.model_dump(mode="json"),
        created_at=now,
    )
    session.add(snapshot)
    receipt.status = "settling"
    changed(session, receipt, actor_id, now, "settlement_started", financial=False)
    emit(session, receipt, "settlement_started", now, snapshot.id)
    return receipt_dto(session, receipt, actor_id)


def report(
    session: Session, receipt: Receipt, actor_id: UUID, version: int, amount: int, now: datetime
) -> ReceiptDTO:
    check_version(receipt, version)
    if receipt.status != "settling" or actor_id == receipt.owner_user_id:
        raise AppError("payment_not_available", "Сообщить перевод можно только при сборе", 409)
    snapshot = current_snapshot(session, receipt)
    member = session.scalars(
        select(Member).where(
            Member.receipt_id == receipt.id, Member.user_id == actor_id, Member.status == "accepted"
        )
    ).one()
    session.add(
        PaymentReport(
            receipt_id=receipt.id,
            member_id=member.id,
            snapshot_id=snapshot.id,
            amount_minor=amount,
            created_at=now,
        )
    )
    changed(session, receipt, actor_id, now, "payment_reported", financial=False)
    emit(session, receipt, "payment_reported", now, snapshot.id)
    return receipt_dto(session, receipt, actor_id)


def record_cash(
    session: Session,
    receipt: Receipt,
    actor_id: UUID,
    member_id: UUID,
    amount: int,
    kind: str,
    reason: str,
    now: datetime,
    *,
    report_id: UUID | None = None,
    correction_of: UUID | None = None,
    direction: int | None = None,
) -> None:
    member = session.scalar(
        select(Member).where(
            Member.id == member_id, Member.receipt_id == receipt.id, Member.status == "accepted"
        )
    )
    if member is None:
        raise AppError("not_found", "Участник недоступен", 404)
    if member.user_id == receipt.owner_user_id or not reason.strip():
        raise AppError("invalid_cash_entry", "Выберите участника и укажите причину")
    sign = 1 if kind == "received" else -1 if kind == "refund" else direction
    if sign not in {-1, 1}:
        raise AppError("invalid_correction", "Укажите направление корректировки")
    if kind == "correction":
        original = session.scalar(
            select(CashLedger).where(
                CashLedger.id == correction_of,
                CashLedger.receipt_id == receipt.id,
                CashLedger.member_id == member_id,
            )
        )
        if original is None:
            raise AppError("invalid_correction", "Выберите исправляемую запись журнала")
    balance = sum(
        e.direction * e.amount_minor
        for e in session.scalars(
            select(CashLedger).where(
                CashLedger.member_id == member_id, CashLedger.receipt_id == receipt.id
            )
        )
    )
    if not 0 <= balance + sign * amount <= 100_000_000:
        raise AppError("invalid_cash_balance", "Некорректный подтверждённый баланс")
    session.add(
        CashLedger(
            receipt_id=receipt.id,
            member_id=member_id,
            amount_minor=amount,
            direction=sign,
            kind=kind,
            actor_id=actor_id,
            report_id=report_id,
            correction_of=correction_of,
            reason=reason.strip(),
            created_at=now,
        )
    )


def review_report(
    session: Session,
    receipt: Receipt,
    actor_id: UUID,
    version: int,
    report_id: UUID,
    decision: str,
    received_amount: int | None,
    now: datetime,
) -> ReceiptDTO:
    require_creator(actor_id, receipt.owner_user_id)
    check_version(receipt, version)
    if receipt.status != "settling":
        raise AppError("receipt_not_settling", "Чек не находится в сборе", 409)
    snapshot = current_snapshot(session, receipt)
    payment = session.scalar(
        select(PaymentReport).where(
            PaymentReport.id == report_id,
            PaymentReport.receipt_id == receipt.id,
            PaymentReport.snapshot_id == snapshot.id,
        )
    )
    if payment is None:
        raise AppError("not_found", "Заявление недоступно", 404)
    if payment.status != "reported":
        raise AppError("report_reviewed", "Заявление уже обработано", 409)
    if decision == "received":
        record_cash(
            session,
            receipt,
            actor_id,
            payment.member_id,
            received_amount if received_amount is not None else payment.amount_minor,
            "received",
            "Создатель подтвердил получение",
            now,
            report_id=payment.id,
        )
    payment.status = decision
    changed(session, receipt, actor_id, now, "payment_reviewed", financial=False)
    emit(session, receipt, "payment_reviewed", now, snapshot.id)
    return receipt_dto(session, receipt, actor_id)


def cash_command(
    session: Session,
    receipt: Receipt,
    actor_id: UUID,
    version: int,
    member_id: UUID,
    amount: int,
    kind: str,
    reason: str,
    now: datetime,
    correction_of: UUID | None,
    direction: int | None,
) -> ReceiptDTO:
    require_creator(actor_id, receipt.owner_user_id)
    check_version(receipt, version)
    if receipt.status != "settling":
        raise AppError("receipt_not_settling", "Сначала зафиксируйте суммы", 409)
    snapshot = current_snapshot(session, receipt)
    record_cash(
        session,
        receipt,
        actor_id,
        member_id,
        amount,
        kind,
        reason,
        now,
        correction_of=correction_of,
        direction=direction,
    )
    changed(session, receipt, actor_id, now, "cash_recorded", financial=False)
    emit(session, receipt, "cash_recorded", now, snapshot.id)
    return receipt_dto(session, receipt, actor_id)


def return_to_collecting(
    session: Session, receipt: Receipt, actor_id: UUID, version: int, reason: str, now: datetime
) -> ReceiptDTO:
    require_creator(actor_id, receipt.owner_user_id)
    check_version(receipt, version)
    try:
        validate_transition(
            ReceiptStatus(receipt.status), ReceiptStatus.COLLECTING, creator=True, reason=reason
        )
    except StateError as exc:
        raise AppError("invalid_transition", str(exc), 409) from exc
    snapshot = current_snapshot(session, receipt)
    snapshot.superseded_at = now
    for payment in session.scalars(
        select(PaymentReport).where(
            PaymentReport.receipt_id == receipt.id, PaymentReport.status == "reported"
        )
    ):
        payment.status = "superseded"
    receipt.status = "collecting"
    changed(session, receipt, actor_id, now, "returned_to_collecting")
    emit(session, receipt, "returned_to_collecting", now)
    return receipt_dto(session, receipt, actor_id)


def close(
    session: Session, receipt: Receipt, actor_id: UUID, version: int, now: datetime
) -> ReceiptDTO:
    require_creator(actor_id, receipt.owner_user_id)
    check_version(receipt, version)
    snapshot = current_snapshot(session, receipt)
    dto = receipt_dto(session, receipt, actor_id)
    assert dto.calculation is not None
    owner = session.scalars(
        select(Member).where(
            Member.receipt_id == receipt.id, Member.user_id == receipt.owner_user_id
        )
    ).one()
    try:
        validate_close(
            status=ReceiptStatus(receipt.status),
            creator=True,
            snapshot_current=snapshot.revision == receipt.financial_revision,
            owner_id=str(owner.id),
            due={key: value.due_minor for key, value in dto.calculation.members.items()},
            cash=dto.cash_balances,
            has_reports=any(p.status == "reported" for p in dto.payment_reports),
        )
    except StateError as exc:
        raise AppError("close_blocked", str(exc), 409) from exc
    receipt.status, receipt.closed_at, receipt.purge_at = "closed", now, now + timedelta(days=7)
    changed(session, receipt, actor_id, now, "receipt_closed", financial=False)
    emit(session, receipt, "receipt_closed", now, snapshot.id)
    return receipt_dto(session, receipt, actor_id)
