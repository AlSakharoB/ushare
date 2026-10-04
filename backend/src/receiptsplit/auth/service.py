import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from receiptsplit.api.errors import AppError
from receiptsplit.auth.telegram import TelegramUser
from receiptsplit.db.auth_models import RateBucket, User, UserSession


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def rate_limit(session: Session, scope: str, key: str, now: datetime, limit: int) -> None:
    window = int(now.timestamp()) // 60
    statement = insert(RateBucket).values(
        id=uuid4(), scope=scope, key=digest(key), window=window, count=1
    )
    returning_statement = statement.on_conflict_do_update(
        index_elements=["scope", "key", "window"], set_={"count": RateBucket.count + 1}
    ).returning(RateBucket.count)
    count = session.scalar(returning_statement)
    session.execute(delete(RateBucket).where(RateBucket.window < window - 60))
    if count is not None and count > limit:
        raise AppError("rate_limited", "Слишком много запросов. Попробуйте через минуту", 429)


def upsert_user(session: Session, identity: TelegramUser, now: datetime) -> User:
    statement = insert(User).values(
        id=uuid4(),
        telegram_id=identity.id,
        username=identity.username,
        display_name=(identity.first_name + " " + identity.last_name).strip()[:256],
        created_at=now,
    )
    returning_statement = statement.on_conflict_do_update(
        index_elements=["telegram_id"],
        set_={
            "username": statement.excluded.username,
            "display_name": statement.excluded.display_name,
        },
    ).returning(User)
    return session.scalars(returning_statement).one()


def new_session(session: Session, user: User, now: datetime) -> tuple[str, str]:
    session.execute(delete(UserSession).where(UserSession.expires_at <= now))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session.add(
        UserSession(
            token_digest=digest(token),
            user_id=user.id,
            csrf_digest=digest(csrf),
            expires_at=now + timedelta(hours=12),
        )
    )
    return token, csrf
