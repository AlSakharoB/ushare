from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ReceiptStatus(StrEnum):
    DRAFT = "draft"
    COLLECTING = "collecting"
    SETTLING = "settling"
    CLOSED = "closed"


class StateError(ValueError):
    pass


@dataclass(frozen=True)
class Revision:
    version: int = 1
    financial: int = 1

    def change(self, financial: bool) -> "Revision":
        return Revision(self.version + 1, self.financial + int(financial))


def validate_transition(
    current: ReceiptStatus,
    target: ReceiptStatus,
    *,
    creator: bool,
    positive_items: bool = False,
    reviewed: bool = False,
    fully_assigned: bool = False,
    all_confirmed: bool = False,
    pending_invitations: bool = True,
    reason: str = "",
) -> None:
    if not creator:
        raise StateError("Только создатель изменяет состояние чека")
    if (current, target) == (ReceiptStatus.DRAFT, ReceiptStatus.COLLECTING):
        if positive_items and reviewed:
            return
    elif (current, target) == (ReceiptStatus.COLLECTING, ReceiptStatus.SETTLING):
        if (
            positive_items
            and reviewed
            and fully_assigned
            and all_confirmed
            and not pending_invitations
        ):
            return
    elif (current, target) == (ReceiptStatus.SETTLING, ReceiptStatus.COLLECTING):
        if reason.strip():
            return
    raise StateError("Переход невозможен: проверьте позиции, доли, подтверждения и приглашения")


def verified_net(received: int, refunded: int) -> int:
    if type(received) is not int or type(refunded) is not int or received < 0 or refunded < 0:
        raise StateError("Некорректный денежный баланс")
    return received - refunded


def validate_close(
    *,
    status: ReceiptStatus,
    creator: bool,
    snapshot_current: bool,
    owner_id: str,
    due: Mapping[str, int],
    cash: Mapping[str, int],
    has_reports: bool,
) -> None:
    if not creator or status != ReceiptStatus.SETTLING or not snapshot_current or has_reports:
        raise StateError("Закрытие требует актуального расчёта и решения всех заявлений")
    if owner_id not in due or any(value < 0 for value in due.values()):
        raise StateError("Некорректный snapshot")
    if any(cash.get(key, 0) != amount for key, amount in due.items() if key != owner_id):
        raise StateError("Есть недоплата или требуется возврат")
