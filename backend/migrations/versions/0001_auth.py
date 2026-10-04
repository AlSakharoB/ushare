"""Telegram users, opaque sessions and shared rate limits."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = "0000"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("username", sa.String(64)),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_sessions",
        sa.Column("token_digest", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("csrf_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user", "user_sessions", ["user_id"])
    op.create_index("ix_sessions_expiry", "user_sessions", ["expires_at"])
    op.create_table(
        "rate_buckets",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("window", sa.BigInteger, nullable=False),
        sa.Column("count", sa.Integer, nullable=False),
        sa.UniqueConstraint("scope", "key", "window"),
    )
    op.create_index("ix_rate_window", "rate_buckets", ["window"])


def downgrade() -> None:
    op.drop_table("rate_buckets")
    op.drop_table("user_sessions")
    op.drop_table("users")
