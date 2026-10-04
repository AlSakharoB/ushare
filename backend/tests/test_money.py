from itertools import permutations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from receiptsplit.domain.money import (
    Discount,
    Line,
    Money,
    MoneyError,
    ShareBasisPoints,
    Tips,
    calculate,
    largest_remainder,
)
from receiptsplit.domain.states import (
    ReceiptStatus,
    Revision,
    StateError,
    validate_close,
    validate_transition,
    verified_net,
)

A = "00000000-0000-0000-0000-000000000001"
B = "00000000-0000-0000-0000-000000000002"
C = "00000000-0000-0000-0000-000000000003"


@pytest.mark.parametrize(
    "total,shares,discount,tips,expected",
    [
        (
            100000,
            {A: 4000, B: 6000},
            Discount("percent", 1000),
            Tips("percent", 1000),
            (39600, 59400, 0),
        ),
        (10001, {A: 5000, B: 5000}, Discount(), Tips(), (5001, 5000, 0)),
        (10000, {A: 3333, B: 3333, C: 3334}, Discount(), Tips(), (3333, 3333, 3334)),
        (100000, {A: 2500}, Discount("fixed", 10000), Tips("fixed", 9000), (24750, 0, 0)),
        (
            100000,
            {A: 4000, B: 6000},
            Discount("percent", 10000),
            Tips("fixed", 10000),
            (4000, 6000, 0),
        ),
        (100000, {A: 4000, B: 6000}, Discount("percent", 10000), Tips("percent", 1000), (0, 0, 0)),
    ],
)
def test_reference_examples(
    total: int,
    shares: dict[str, int],
    discount: Discount,
    tips: Tips,
    expected: tuple[int, int, int],
) -> None:
    result = calculate([Line("line", total, shares)], [A, B, C], A, discount, tips)
    assert tuple(result.members[key].due_minor for key in [A, B, C]) == expected
    assert (
        sum(cost.due_minor for cost in result.members.values()) + result.unassigned_minor
        == result.total_minor
    )
    if shares == {A: 2500}:
        assert result.unassigned_minor == 74250


def test_e2e01_exact_reference() -> None:
    result = calculate(
        [Line("pizza", 120000, {A: 5000, B: 5000}), Line("drinks", 60000, {B: 5000, C: 5000})],
        [A, B, C],
        A,
        Discount("percent", 1000),
        Tips("percent", 1000),
    )
    assert result.total_minor == 178200
    assert [result.members[key].due_minor for key in [A, B, C]] == [59400, 89100, 29700]
    assert result.own_cost_minor == 59400
    assert result.expected_from_others_minor == 118800


@given(
    total=st.integers(1, 1_000_000),
    left=st.integers(0, 10000),
    discount_bp=st.integers(0, 10000),
    tip_bp=st.integers(0, 10000),
    remaining=st.integers(0, 10000),
)
@settings(max_examples=300)
def test_conservation_and_bounds(
    total: int, left: int, discount_bp: int, tip_bp: int, remaining: int
) -> None:
    right = min(remaining, 10000 - left)
    result = calculate(
        [Line("l", total, {A: left, B: right})],
        [A, B, C],
        A,
        Discount("percent", discount_bp),
        Tips("percent", tip_bp),
    )
    assert (
        sum(c.due_minor for c in result.members.values()) + result.unassigned_minor
        == result.total_minor
    )
    assert sum(c.discount_minor for c in result.members.values()) <= result.discount_minor
    assert all(0 <= c.discount_minor <= c.base_minor for c in result.members.values())
    assert result.members[C].due_minor == 0
    assert result.own_cost_minor + result.expected_from_others_minor == result.total_minor
    assert result.to_dict()["total_minor"] == result.total_minor


@given(
    amount=st.integers(0, 1_000_000),
    weights=st.lists(st.integers(1, 10000), min_size=3, max_size=3),
)
def test_remainder_deterministic_and_conserves(amount: int, weights: list[int]) -> None:
    pairs = list(zip([A, B, C], weights, strict=True))
    expected = largest_remainder(amount, dict(pairs))
    for ordered in permutations(pairs):
        assert largest_remainder(amount, dict(ordered)) == expected
    assert sum(expected.values()) == amount
    total = sum(weights)
    assert all(
        amount * weight // total <= expected[key] <= amount * weight // total + 1
        for key, weight in pairs
    )


def test_line_and_member_order_independent() -> None:
    first = Line("a", 10001, {A: 5000, B: 5000})
    second = Line("b", 333, {A: 3333, B: 6667})
    assert calculate([first, second], [A, B], A) == calculate([second, first], [B, A], A)


@pytest.mark.parametrize("raw", ["-1", "NaN", "Infinity", "0.001", "1000000.01", "bad"])
def test_invalid_money(raw: str) -> None:
    with pytest.raises(MoneyError):
        Money.parse(raw)


def test_exact_parse_and_half_up() -> None:
    assert Money.parse("1 234,56").minor == 123456
    assert Money(123456).format() == "1 234,56 ₽"
    assert ShareBasisPoints.parse("33,33").bp == 3333
    assert Discount("percent", 5000).amount(1) == 1
    assert calculate([], [A], A).total_minor == 0
    assert calculate([Line("x", 100, {A: 0, B: 10000})], [A, B], A).own_cost_minor == 0


@pytest.mark.parametrize("value", [-1, 100_000_001, True, 1.0])
def test_invalid_integer_money(value: int) -> None:
    with pytest.raises(MoneyError):
        Money(value)


def test_invalid_percent_discount_and_total_share() -> None:
    with pytest.raises(MoneyError):
        ShareBasisPoints(10001)
    with pytest.raises(MoneyError):
        Line("l", 1, {A: 6000, B: 6000})
    with pytest.raises(MoneyError):
        calculate([Line("l", 100, {})], [A], A, Discount("fixed", 101))
    with pytest.raises(MoneyError):
        largest_remainder(1, {A: 0})


def test_state_guards_and_money_preserved_after_repricing() -> None:
    validate_transition(
        ReceiptStatus.COLLECTING,
        ReceiptStatus.SETTLING,
        creator=True,
        positive_items=True,
        reviewed=True,
        fully_assigned=True,
        all_confirmed=True,
        pending_invitations=False,
    )
    with pytest.raises(StateError):
        validate_transition(ReceiptStatus.CLOSED, ReceiptStatus.COLLECTING, creator=True)
    with pytest.raises(StateError):
        validate_transition(ReceiptStatus.SETTLING, ReceiptStatus.COLLECTING, creator=True)
    validate_transition(
        ReceiptStatus.SETTLING, ReceiptStatus.COLLECTING, creator=True, reason="Цена исправлена"
    )
    for net in [0, 50000, 60000]:
        with pytest.raises(StateError):
            validate_close(
                status=ReceiptStatus.SETTLING,
                creator=True,
                snapshot_current=True,
                owner_id=A,
                due={A: 0, B: 40000},
                cash={B: net},
                has_reports=False,
            )
    validate_close(
        status=ReceiptStatus.SETTLING,
        creator=True,
        snapshot_current=True,
        owner_id=A,
        due={A: 0, B: 40000},
        cash={B: verified_net(50000, 10000)},
        has_reports=False,
    )
    with pytest.raises(StateError):
        validate_close(
            status=ReceiptStatus.SETTLING,
            creator=True,
            snapshot_current=True,
            owner_id=A,
            due={A: 0, B: 40000},
            cash={B: 40000},
            has_reports=True,
        )
    with pytest.raises(StateError):
        validate_close(
            status=ReceiptStatus.SETTLING,
            creator=False,
            snapshot_current=True,
            owner_id=A,
            due={A: 0, B: 0},
            cash={},
            has_reports=False,
        )
    validate_close(
        status=ReceiptStatus.SETTLING,
        creator=True,
        snapshot_current=True,
        owner_id=A,
        due={A: 0, B: 0},
        cash={},
        has_reports=False,
    )
    assert Revision().change(False) == Revision(2, 1)
    assert Revision().change(True) == Revision(2, 2)
