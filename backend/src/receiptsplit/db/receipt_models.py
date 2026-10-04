from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from receiptsplit.db.session import Base


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (
        CheckConstraint("status IN ('draft','collecting','settling','closed')"),
        CheckConstraint("version > 0 AND financial_revision > 0"),
        CheckConstraint(
            "discount_mode IN ('fixed','percent') AND tips_mode IN ('fixed','percent')"
        ),
        CheckConstraint(
            "discount_value BETWEEN 0 AND 100000000 AND tips_value BETWEEN 0 AND 100000000"
        ),
        CheckConstraint("discount_mode <> 'percent' OR discount_value <= 10000"),
        CheckConstraint("tips_mode <> 'percent' OR tips_value <= 10000"),
        CheckConstraint("(status = 'closed') = (closed_at IS NOT NULL AND purge_at IS NOT NULL)"),
        CheckConstraint(
            "printed_total_minor IS NULL OR printed_total_minor BETWEEN 0 AND 100000000"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    version: Mapped[int] = mapped_column(default=1)
    financial_revision: Mapped[int] = mapped_column(default=1)
    discount_mode: Mapped[str] = mapped_column(String(8), default="fixed")
    discount_value: Mapped[int] = mapped_column(BigInteger, default=0)
    tips_mode: Mapped[str] = mapped_column(String(8), default="fixed")
    tips_value: Mapped[int] = mapped_column(BigInteger, default=0)
    printed_total_minor: Mapped[int | None] = mapped_column(BigInteger)
    printed_total_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Member(Base):
    __tablename__ = "receipt_members"
    __table_args__ = (
        UniqueConstraint("receipt_id", "user_id"),
        UniqueConstraint("id", "receipt_id"),
        CheckConstraint("role IN ('creator','participant')"),
        CheckConstraint("status IN ('accepted','pending')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="accepted")
    confirmed_revision: Mapped[int | None]


class Item(Base):
    __tablename__ = "receipt_items"
    __table_args__ = (
        UniqueConstraint("id", "receipt_id"),
        CheckConstraint("line_total_minor BETWEEN 1 AND 100000000"),
        CheckConstraint("quantity > 0 AND quantity <= 1000000"),
        CheckConstraint("unit_price_minor IS NULL OR unit_price_minor BETWEEN 0 AND 100000000"),
        CheckConstraint("origin IN ('manual','ocr')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    sort_order: Mapped[int] = mapped_column(default=0)
    name: Mapped[str] = mapped_column(String(256))
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 6))
    unit_price_minor: Mapped[int | None] = mapped_column(BigInteger)
    line_total_minor: Mapped[int] = mapped_column(BigInteger)
    mismatch_reason: Mapped[str | None] = mapped_column(String(500))
    origin: Mapped[str] = mapped_column(String(8), default="manual")
    reviewed: Mapped[bool] = mapped_column(default=True)


class Share(Base):
    __tablename__ = "item_shares"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "receipt_id"],
            ["receipt_items.id", "receipt_items.receipt_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["member_id", "receipt_id"],
            ["receipt_members.id", "receipt_members.receipt_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("share_bp BETWEEN 1 AND 10000"),
    )
    item_id: Mapped[UUID] = mapped_column(primary_key=True)
    member_id: Mapped[UUID] = mapped_column(primary_key=True)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    share_bp: Mapped[int]


class AuditEvent(Base):
    __tablename__ = "receipt_audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    event: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String(180), primary_key=True)
    key_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    receipt_id: Mapped[UUID | None] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
