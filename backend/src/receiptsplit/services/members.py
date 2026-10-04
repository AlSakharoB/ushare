from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from receiptsplit.api.errors import AppError
from receiptsplit.db.auth_models import User
from receiptsplit.db.member_models import Invitation
from receiptsplit.db.receipt_models import Member, Receipt


def known_contacts(session: Session, user_id: UUID) -> list[User]:
    own, other = aliased(Member), aliased(Member)
    query = (
        select(User)
        .join(other, other.user_id == User.id)
        .join(own, own.receipt_id == other.receipt_id)
        .where(
            own.user_id == user_id,
            own.status == "accepted",
            other.status == "accepted",
            other.user_id != user_id,
        )
        .distinct()
    )
    return list(session.scalars(query).all())


def resolve_invitation(
    session: Session, token_digest: str, user: User, now: datetime
) -> tuple[Invitation, Receipt]:
    invitation = session.scalar(select(Invitation).where(Invitation.token_digest == token_digest))
    if invitation is None:
        raise AppError("not_found", "Приглашение недоступно", 404)
    receipt = session.scalar(
        select(Receipt).where(Receipt.id == invitation.receipt_id).with_for_update()
    )
    if receipt is None:
        raise AppError("not_found", "Приглашение недоступно", 404)
    session.refresh(invitation)
    if (
        receipt is None
        or receipt.status not in {"draft", "collecting"}
        or invitation.expires_at <= now
        or invitation.revoked_at is not None
    ):
        raise AppError("not_found", "Приглашение недоступно", 404)
    if (
        invitation.target_telegram_id is not None
        and invitation.target_telegram_id != user.telegram_id
    ):
        raise AppError("invitation_target", "Приглашение адресовано другому пользователю", 403)
    return invitation, receipt
