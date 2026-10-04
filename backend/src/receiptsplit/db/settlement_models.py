from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from receiptsplit.db.session import Base


class Snapshot(Base):
    __tablename__ = "settlement_snapshots"
    __table_args__ = (
        UniqueConstraint("id", "receipt_id"),
        Index(
            "uq_current_snapshot",
            "receipt_id",
            unique=True,
            postgresql_where=text("superseded_at IS NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int]
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentReport(Base):
    __tablename__ = "payment_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["member_id", "receipt_id"], ["receipt_members.id", "receipt_members.receipt_id"]
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "receipt_id"],
            ["settlement_snapshots.id", "settlement_snapshots.receipt_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "receipt_id"),
        CheckConstraint("amount_minor BETWEEN 1 AND 100000000"),
        CheckConstraint("status IN ('reported','received','rejected','duplicate','superseded')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[UUID]
    snapshot_id: Mapped[UUID]
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="reported")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CashLedger(Base):
    __tablename__ = "cash_ledger"
    __table_args__ = (
        ForeignKeyConstraint(
            ["member_id", "receipt_id"], ["receipt_members.id", "receipt_members.receipt_id"]
        ),
        ForeignKeyConstraint(
            ["report_id", "receipt_id"], ["payment_reports.id", "payment_reports.receipt_id"]
        ),
        UniqueConstraint("id", "receipt_id"),
        CheckConstraint("amount_minor BETWEEN 1 AND 100000000"),
        CheckConstraint("kind IN ('received','refund','correction')"),
        CheckConstraint("direction IN (-1,1)"),
        CheckConstraint(
            "(kind <> 'received' OR direction=1) AND (kind <> 'refund' OR direction=-1)"
        ),
        CheckConstraint("kind <> 'correction' OR correction_of IS NOT NULL"),
        ForeignKeyConstraint(
            ["correction_of", "receipt_id"], ["cash_ledger.id", "cash_ledger.receipt_id"]
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[UUID]
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    direction: Mapped[int]
    kind: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    report_id: Mapped[UUID | None]
    correction_of: Mapped[UUID | None]
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[UUID | None]
    attempts: Mapped[int] = mapped_column(default=0)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
