import hmac
from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from receiptsplit.api.errors import AppError
from receiptsplit.auth.service import digest, rate_limit
from receiptsplit.db.auth_models import User, UserSession


def db_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session, session.begin():
        yield session


def require_origin(request: Request) -> None:
    if request.headers.get("origin") != request.app.state.settings.public_origin:
        raise AppError("origin_rejected", "Недопустимый источник запроса", 403)


def actor(request: Request, session: Session = Depends(db_session)) -> User:
    token = request.cookies.get("receiptsplit_session", "")
    auth_session = session.get(UserSession, digest(token)) if token else None
    if auth_session is None or auth_session.expires_at <= request.app.state.clock.now():
        raise AppError("authentication_required", "Откройте приложение заново через Telegram", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not hmac.compare_digest(digest(csrf), auth_session.csrf_digest):
            raise AppError("csrf_rejected", "Обновите сессию приложения", 403)
    user = session.get(User, auth_session.user_id)
    if user is None:
        raise AppError("authentication_required", "Войдите снова", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        with Session(request.app.state.engine) as rate_session, rate_session.begin():
            rate_limit(rate_session, "mutation", str(user.id), request.app.state.clock.now(), 120)
    return user
