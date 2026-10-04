from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

MAX_MINOR = 100_000_000
UNASSIGNED = "~unassigned"


class MoneyError(ValueError):
    pass


def bounded_integer(value: int, maximum: int = MAX_MINOR) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise MoneyError("Сумма или процент вне допустимого диапазона")
    return value


def parse_decimal_units(raw: str, maximum: int = MAX_MINOR) -> int:
    try:
        value = Decimal(raw.strip().replace(" ", "").replace("\u00a0", "").replace(",", "."))
        if not value.is_finite() or value < 0 or value > Decimal(maximum) / 100:
            raise MoneyError("Некорректное значение")
        units = value * 100
        if units != units.to_integral_value():
            raise MoneyError("Не более двух знаков после запятой")
        return bounded_integer(int(units), maximum)
    except (InvalidOperation, TypeError) as exc:
        raise MoneyError("Некорректное значение") from exc


@dataclass(frozen=True)
class Money:
    minor: int

    def __post_init__(self) -> None:
        bounded_integer(self.minor)

    @classmethod
    def parse(cls, raw: str) -> "Money":
        return cls(parse_decimal_units(raw))

    def format(self) -> str:
        return f"{self.minor // 100:,}".replace(",", " ") + f",{self.minor % 100:02d} ₽"


@dataclass(frozen=True)
class ShareBasisPoints:
    bp: int

    def __post_init__(self) -> None:
        bounded_integer(self.bp, 10000)

    @classmethod
    def parse(cls, raw: str) -> "ShareBasisPoints":
        return cls(parse_decimal_units(raw, 10000))


@dataclass(frozen=True)
class Adjustment:
    mode: Literal["fixed", "percent"] = "fixed"
    value: int = 0

    def __post_init__(self) -> None:
        if self.mode not in {"fixed", "percent"}:
            raise MoneyError("Неизвестный режим")
        bounded_integer(self.value, 10000 if self.mode == "percent" else MAX_MINOR)

    def amount(self, base: int) -> int:
        bounded_integer(base)
        # Exact round_half_up for nonnegative rational cents.
        return self.value if self.mode == "fixed" else (base * self.value + 5000) // 10000


@dataclass(frozen=True)
class Discount(Adjustment):
    pass


@dataclass(frozen=True)
class Tips(Adjustment):
    pass


def largest_remainder(amount: int, weights: Mapping[str, int]) -> dict[str, int]:
    bounded_integer(amount)
    if any(type(weight) is not int or weight < 0 for weight in weights.values()):
        raise MoneyError("Веса должны быть неотрицательными целыми")
    total = sum(weights.values())
    if total == 0:
        if amount:
            raise MoneyError("Нельзя распределить сумму без весов")
        return {key: 0 for key in weights}
    result = {key: amount * weight // total for key, weight in weights.items()}
    order = sorted(weights, key=lambda key: (-(amount * weights[key] % total), key))
    for key in order[: amount - sum(result.values())]:
        result[key] += 1
    return result


@dataclass(frozen=True)
class Line:
    id: str
    total_minor: int
    shares: Mapping[str, int]

    def __post_init__(self) -> None:
        if bounded_integer(self.total_minor) == 0:
            raise MoneyError("Стоимость позиции должна быть положительной")
        if UNASSIGNED in self.shares:
            raise MoneyError("Зарезервированный участник")
        for share in self.shares.values():
            ShareBasisPoints(share)
        if sum(self.shares.values()) > 10000:
            raise MoneyError("Сумма долей превышает 100%")


@dataclass(frozen=True)
class MemberCost:
    base_minor: int
    discount_minor: int
    tips_minor: int
    due_minor: int


@dataclass(frozen=True)
class Calculation:
    subtotal_minor: int
    discount_minor: int
    tips_minor: int
    total_minor: int
    members: dict[str, MemberCost]
    unassigned_minor: int
    own_cost_minor: int
    expected_from_others_minor: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def calculate(
    lines: Sequence[Line],
    member_ids: Sequence[str],
    owner_id: str,
    discount: Discount = Discount(),
    tips: Tips = Tips(),
) -> Calculation:
    if (
        owner_id not in member_ids
        or len(set(member_ids)) != len(member_ids)
        or UNASSIGNED in member_ids
    ):
        raise MoneyError("Некорректный состав участников")
    if len({line.id for line in lines}) != len(lines):
        raise MoneyError("Дублирующиеся позиции")
    subtotal = bounded_integer(sum(line.total_minor for line in lines))
    bases = dict.fromkeys([*member_ids, UNASSIGNED], 0)
    for line in lines:
        if not set(line.shares).issubset(member_ids):
            raise MoneyError("Доля неизвестного участника")
        weights = {key: bp for key, bp in line.shares.items() if bp}
        weights[UNASSIGNED] = 10000 - sum(weights.values())
        for key, amount in largest_remainder(line.total_minor, weights).items():
            bases[key] += amount
    discount_amount = discount.amount(subtotal)
    if discount_amount > subtotal:
        raise MoneyError("Скидка превышает стоимость чека")
    discounts = largest_remainder(discount_amount, bases)
    net = {key: base - discounts[key] for key, base in bases.items()}
    tips_amount = tips.amount(subtotal - discount_amount)
    total = bounded_integer(subtotal - discount_amount + tips_amount)
    tip_parts = largest_remainder(tips_amount, net if sum(net.values()) else bases)
    costs = {
        key: MemberCost(base, discounts[key], tip_parts[key], net[key] + tip_parts[key])
        for key, base in bases.items()
    }
    unassigned = costs.pop(UNASSIGNED).due_minor
    own = costs[owner_id].due_minor
    return Calculation(
        subtotal,
        discount_amount,
        tips_amount,
        total,
        costs,
        unassigned,
        own,
        total - own,
    )
