import secrets
from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from receiptsplit.api.errors import AppError
from receiptsplit.api.receipts import DB, Actor
from receiptsplit.auth.policy import require_creator
from receiptsplit.auth.service import digest
from receiptsplit.contracts import Command, ReceiptDTO
from receiptsplit.db.auth_models import User
from receiptsplit.db.member_models import Invitation, JoinRequest
from receiptsplit.db.receipt_models import Member, Share
from receiptsplit.services.members import known_contacts, resolve_invitation
from receiptsplit.services.receipts import changed, editable, get_receipt, receipt_dto

router = APIRouter(prefix="/api/v1")


class InviteCommand(Command):
    target_telegram_id: Annotated[int, Field(strict=True, gt=0, lt=2**52)] | None = None


class TokenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=128)


class AddMember(Command):
    user_id: UUID


class ReviewRequest(Command):
    approve: bool


class InvitationDTO(BaseModel):
    id: UUID
    receipt_id: UUID
    token: str
    expires_at: datetime
    version: int


class InvitationPreview(BaseModel):
    receipt_id: UUID
    title: str
    creator: str
    targeted: bool


class JoinRequestDTO(BaseModel):
    id: UUID | None
    status: str
    receipt_id: UUID


class ContactDTO(BaseModel):
    id: UUID
    telegram_id: int
    display_name: str


class PendingRequestDTO(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str
    status: str


@router.get("/contacts")
def contacts(user: Actor, session: DB) -> list[ContactDTO]:
    return [
        ContactDTO(id=u.id, telegram_id=u.telegram_id, display_name=u.display_name)
        for u in known_contacts(session, user.id)
    ]


@router.get("/receipts/{receipt_id}/members")
def members(receipt_id: UUID, request: Request, user: Actor, session: DB) -> ReceiptDTO:
    return receipt_dto(
        session, get_receipt(session, receipt_id, user.id, request.app.state.clock.now()), user.id
    )


@router.post("/receipts/{receipt_id}/members")
def add_known(
    receipt_id: UUID, body: AddMember, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    receipt = get_receipt(session, receipt_id, user.id, now, lock=True)
    editable(receipt, user.id, body.expected_version)
    if body.user_id not in {u.id for u in known_contacts(session, user.id)}:
        raise AppError("unknown_contact", "Используйте приглашение для нового участника")
    if (
        session.scalar(
            select(Member.id).where(Member.receipt_id == receipt_id, Member.user_id == body.user_id)
        )
        is None
    ):
        session.add(Member(receipt_id=receipt_id, user_id=body.user_id, role="participant"))
        changed(session, receipt, user.id, now, "member_added")
    return receipt_dto(session, receipt, user.id)


@router.post("/receipts/{receipt_id}/invitations")
def invite(
    receipt_id: UUID, body: InviteCommand, request: Request, user: Actor, session: DB
) -> InvitationDTO:
    now = request.app.state.clock.now()
    receipt = get_receipt(session, receipt_id, user.id, now, lock=True)
    editable(receipt, user.id, body.expected_version)
    if body.target_telegram_id is not None and body.target_telegram_id not in {
        u.telegram_id for u in known_contacts(session, user.id)
    }:
        raise AppError("unknown_contact", "Адресное приглашение доступно для собственных контактов")
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        receipt_id=receipt_id,
        token_digest=digest(token),
        target_telegram_id=body.target_telegram_id,
        expires_at=now + timedelta(hours=72),
    )
    session.add(invitation)
    changed(session, receipt, user.id, now, "invitation_created", financial=False)
    return InvitationDTO(
        id=invitation.id,
        receipt_id=receipt_id,
        token=token,
        expires_at=invitation.expires_at,
        version=receipt.version,
    )


@router.post("/invitations/resolve")
def preview(body: TokenBody, request: Request, user: Actor, session: DB) -> InvitationPreview:
    invitation, receipt = resolve_invitation(
        session, digest(body.token), user, request.app.state.clock.now()
    )
    creator = session.get(User, receipt.owner_user_id)
    assert creator is not None
    return InvitationPreview(
        receipt_id=receipt.id,
        title=receipt.title,
        creator=creator.display_name,
        targeted=invitation.target_telegram_id is not None,
    )


@router.post("/join-requests")
def join(body: TokenBody, request: Request, user: Actor, session: DB) -> JoinRequestDTO:
    now = request.app.state.clock.now()
    invitation, receipt = resolve_invitation(session, digest(body.token), user, now)
    if session.scalar(
        select(Member.id).where(
            Member.receipt_id == receipt.id, Member.user_id == user.id, Member.status == "accepted"
        )
    ):
        return JoinRequestDTO(id=None, status="approved", receipt_id=receipt.id)
    pending = session.scalar(
        select(JoinRequest).where(
            JoinRequest.receipt_id == receipt.id, JoinRequest.user_id == user.id
        )
    )
    if pending and pending.status == "pending":
        return JoinRequestDTO(id=pending.id, status=pending.status, receipt_id=receipt.id)
    if invitation.target_telegram_id is not None:
        if invitation.consumed_at is not None:
            raise AppError("not_found", "Приглашение уже использовано", 404)
        session.add(Member(receipt_id=receipt.id, user_id=user.id, role="participant"))
        invitation.consumed_at = now
        changed(session, receipt, user.id, now, "targeted_invitation_accepted")
        return JoinRequestDTO(id=None, status="approved", receipt_id=receipt.id)
    if pending is None:
        pending = JoinRequest(
            receipt_id=receipt.id, user_id=user.id, invitation_id=invitation.id, created_at=now
        )
        session.add(pending)
    else:
        pending.invitation_id, pending.status = invitation.id, "pending"
    changed(session, receipt, user.id, now, "join_requested", financial=False)
    return JoinRequestDTO(id=pending.id, status=pending.status, receipt_id=receipt.id)


@router.get("/receipts/{receipt_id}/join-requests")
def pending_requests(
    receipt_id: UUID, request: Request, user: Actor, session: DB
) -> list[PendingRequestDTO]:
    receipt = get_receipt(session, receipt_id, user.id, request.app.state.clock.now())
    require_creator(user.id, receipt.owner_user_id)
    rows = session.execute(
        select(JoinRequest, User)
        .join(User, User.id == JoinRequest.user_id)
        .where(JoinRequest.receipt_id == receipt_id, JoinRequest.status == "pending")
    ).all()
    return [
        PendingRequestDTO(id=j.id, user_id=u.id, display_name=u.display_name, status=j.status)
        for j, u in rows
    ]


@router.post("/receipts/{receipt_id}/join-requests/{join_id}/review")
def review(
    receipt_id: UUID, join_id: UUID, body: ReviewRequest, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    receipt = get_receipt(session, receipt_id, user.id, now, lock=True)
    editable(receipt, user.id, body.expected_version)
    pending = session.scalar(
        select(JoinRequest).where(JoinRequest.id == join_id, JoinRequest.receipt_id == receipt_id)
    )
    if pending is None:
        raise AppError("not_found", "Заявка недоступна", 404)
    if pending.status != "pending":
        return receipt_dto(session, receipt, user.id)
    invitation = session.get(Invitation, pending.invitation_id)
    if body.approve and (
        invitation is None or invitation.revoked_at is not None or invitation.expires_at <= now
    ):
        raise AppError("invitation_expired", "Приглашение недоступно", 409)
    pending.status = "approved" if body.approve else "rejected"
    if (
        body.approve
        and session.scalar(
            select(Member.id).where(
                Member.receipt_id == receipt_id, Member.user_id == pending.user_id
            )
        )
        is None
    ):
        session.add(Member(receipt_id=receipt_id, user_id=pending.user_id, role="participant"))
    changed(session, receipt, user.id, now, "join_request_reviewed", financial=body.approve)
    return receipt_dto(session, receipt, user.id)


@router.post("/receipts/{receipt_id}/invitations/{invitation_id}/revoke")
def revoke(
    receipt_id: UUID, invitation_id: UUID, body: Command, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    receipt = get_receipt(session, receipt_id, user.id, now, lock=True)
    editable(receipt, user.id, body.expected_version)
    invitation = session.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id, Invitation.receipt_id == receipt_id
        )
    )
    if invitation is None:
        raise AppError("not_found", "Приглашение недоступно", 404)
    invitation.revoked_at = now
    for pending in session.scalars(
        select(JoinRequest).where(
            JoinRequest.invitation_id == invitation_id, JoinRequest.status == "pending"
        )
    ):
        pending.status = "rejected"
    changed(session, receipt, user.id, now, "invitation_revoked", financial=False)
    return receipt_dto(session, receipt, user.id)


@router.delete("/receipts/{receipt_id}/members/{member_id}")
def remove_member(
    receipt_id: UUID, member_id: UUID, body: Command, request: Request, user: Actor, session: DB
) -> ReceiptDTO:
    now = request.app.state.clock.now()
    receipt = get_receipt(session, receipt_id, user.id, now, lock=True)
    editable(receipt, user.id, body.expected_version)
    member = session.scalar(
        select(Member).where(Member.id == member_id, Member.receipt_id == receipt_id)
    )
    if member is None:
        raise AppError("not_found", "Участник недоступен", 404)
    if (
        member.user_id == receipt.owner_user_id
        or session.scalar(select(Share.item_id).where(Share.member_id == member_id).limit(1))
        is not None
    ):
        raise AppError(
            "member_has_activity", "Нельзя удалить создателя или участника с долями", 409
        )
    session.execute(
        delete(JoinRequest).where(
            JoinRequest.receipt_id == receipt_id, JoinRequest.user_id == member.user_id
        )
    )
    session.delete(member)
    changed(session, receipt, user.id, now, "member_removed")
    return receipt_dto(session, receipt, user.id)
