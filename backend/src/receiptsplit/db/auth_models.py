from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from receiptsplit.db.session import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_sessions"
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    __table_args__ = (UniqueConstraint("scope", "key", "window"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(64))
    window: Mapped[int] = mapped_column(BigInteger, index=True)
    count: Mapped[int]
