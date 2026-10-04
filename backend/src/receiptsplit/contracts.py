from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Minor = Annotated[int, Field(strict=True, ge=0, le=100_000_000)]
BP = Annotated[int, Field(strict=True, ge=0, le=10000)]
Version = Annotated[int, Field(strict=True, ge=1)]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Version


class ItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=256)
    quantity: str = "1"
    unit_price_minor: Minor | None = None
    line_total_minor: Annotated[int, Field(strict=True, gt=0, le=100_000_000)]
    mismatch_reason: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Пустое название")
        return value.strip()

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: str) -> str:
        try:
            number = Decimal(value.replace(",", "."))
            exponent = number.as_tuple().exponent
            if (
                not number.is_finite()
                or not 0 < number <= 1_000_000
                or not isinstance(exponent, int)
                or exponent < -6
            ):
                raise ValueError("Некорректное количество")
            return str(number)
        except InvalidOperation as exc:
            raise ValueError("Некорректное количество") from exc


class ItemCommand(ItemInput, Command):
    pass


class CreateReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    items: list[ItemInput] = Field(default_factory=list, max_length=500)


class PatchReceipt(Command):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    discount_mode: Literal["fixed", "percent"] | None = None
    discount_value: Minor | None = None
    tips_mode: Literal["fixed", "percent"] | None = None
    tips_value: Minor | None = None
    printed_total_minor: Minor | None = None
    printed_total_reason: str | None = Field(default=None, max_length=500)


class ItemDTO(BaseModel):
    id: UUID
    name: str
    quantity: str
    unit_price_minor: int | None
    line_total_minor: int
    origin: str
    reviewed: bool
    shares: dict[str, int]


class MemberDTO(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str
    role: str
    status: str
    confirmed_revision: int | None


class MemberCostDTO(BaseModel):
    base_minor: int
    discount_minor: int
    tips_minor: int
    due_minor: int


class CalculationDTO(BaseModel):
    subtotal_minor: int
    discount_minor: int
    tips_minor: int
    total_minor: int
    members: dict[str, MemberCostDTO]
    unassigned_minor: int
    own_cost_minor: int
    expected_from_others_minor: int


class ReceiptDTO(BaseModel):
    id: UUID
    title: str
    currency: str
    owner_user_id: UUID
    status: str
    version: int
    financial_revision: int
    created_at: datetime
    closed_at: datetime | None
    purge_at: datetime | None
    discount_mode: str | None
    discount_value: int | None
    tips_mode: str | None
    tips_value: int | None
    printed_total_minor: int | None
    printed_total_reason: str | None
    items: list[ItemDTO]
    members: list[MemberDTO]
    calculation: CalculationDTO | None


class ReceiptPage(BaseModel):
    receipts: list[ReceiptDTO]
    next_cursor: UUID | None
