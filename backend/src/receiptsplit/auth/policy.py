from uuid import UUID

from receiptsplit.api.errors import AppError


def require_creator(actor_id: UUID, owner_id: UUID) -> None:
    if actor_id != owner_id:
        raise AppError("creator_required", "Действие доступно только создателю", 403)


def require_accepted(accepted: bool) -> None:
    if not accepted:
        raise AppError("not_found", "Чек недоступен", 404)
