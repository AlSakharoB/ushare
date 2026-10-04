from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete
from sqlalchemy.orm import Session

from receiptsplit.api.dependencies import actor, db_session, require_origin
from receiptsplit.api.errors import AppError
from receiptsplit.auth.service import digest, new_session, rate_limit, upsert_user
from receiptsplit.auth.telegram import TelegramUser, validate_init_data
from receiptsplit.db.auth_models import User, UserSession

router = APIRouter(prefix="/api/v1")


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    init_data: str = Field(max_length=16384)


class DevLoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    telegram_id: int = Field(gt=0, lt=2**52)
    first_name: str = Field(min_length=1, max_length=128)


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    telegram_id: int
    username: str | None
    display_name: str


class LoginDTO(BaseModel):
    user: UserDTO
    csrf_token: str


def login(
    identity: TelegramUser, request: Request, response: Response, session: Session
) -> LoginDTO:
    settings = request.app.state.settings
    user = upsert_user(session, identity, request.app.state.clock.now())
    token, csrf = new_session(session, user, request.app.state.clock.now())
    response.set_cookie(
        "receiptsplit_session",
        token,
        max_age=43200,
        httponly=True,
        secure=settings.public_origin.startswith("https://"),
        samesite="lax",
        path="/",
    )
    return LoginDTO(user=UserDTO.model_validate(user), csrf_token=csrf)


@router.post("/auth/telegram", dependencies=[Depends(require_origin)])
def telegram_login(
    body: LoginBody, request: Request, response: Response, session: Session = Depends(db_session)
) -> LoginDTO:
    # Commit rate bucket independently, including for invalid signatures.
    with Session(request.app.state.engine) as rate_session, rate_session.begin():
        rate_limit(
            rate_session,
            "auth",
            request.client.host if request.client else "unknown",
            request.app.state.clock.now(),
            20,
        )
    identity = validate_init_data(
        body.init_data, request.app.state.settings.bot_token, request.app.state.clock.now()
    )
    return login(identity, request, response, session)


@router.post("/auth/dev", dependencies=[Depends(require_origin)])
def dev_login(
    body: DevLoginBody, request: Request, response: Response, session: Session = Depends(db_session)
) -> LoginDTO:
    settings = request.app.state.settings
    if (
        settings.app_env != "development"
        or not settings.dev_auth_enabled
        or urlsplit(settings.public_origin).hostname not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise AppError("not_found", "Маршрут недоступен", 404)
    return login(
        TelegramUser(id=body.telegram_id, first_name=body.first_name), request, response, session
    )


@router.get("/me")
def me(user: Annotated[User, Depends(actor)]) -> UserDTO:
    return UserDTO.model_validate(user)


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user: Annotated[User, Depends(actor)],
    session: Session = Depends(db_session),
) -> None:
    session.execute(
        delete(UserSession).where(
            UserSession.token_digest == digest(request.cookies["receiptsplit_session"]),
            UserSession.user_id == user.id,
        )
    )
    response.delete_cookie("receiptsplit_session", path="/")
