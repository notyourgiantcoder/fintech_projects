"""Currency-aware money primitives.

All monetary values in the engine are `Decimal`, never `float`, and are rounded
to 2 decimal places (cents / paise) with ROUND_HALF_UP.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

CENT = Decimal("0.01")


class Currency(StrEnum):
    INR = "INR"
    USD = "USD"

    @property
    def symbol(self) -> str:
        return {"INR": "₹", "USD": "$"}[self.value]


class CurrencyMismatchError(ValueError):
    """Raised when arithmetic mixes two currencies without an explicit FX conversion."""


def quantize(value: Decimal | int | str) -> Decimal:
    """Round to 2 dp with ROUND_HALF_UP (what users expect on statements)."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _group_indian(integer_digits: str) -> str:
    # Indian grouping: last 3 digits, then groups of 2 -> 12,34,567
    if len(integer_digits) <= 3:
        return integer_digits
    head, tail = integer_digits[:-3], integer_digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def format_amount(amount: Decimal, currency: Currency) -> str:
    """Format for display: ₹12,34,567.50 (Indian grouping) or $1,234,567.50."""
    q = quantize(amount)
    sign = "-" if q < 0 else ""
    integer_part, _, fraction = f"{abs(q):.2f}".partition(".")
    grouped = _group_indian(integer_part) if currency is Currency.INR else f"{int(integer_part):,}"
    return f"{sign}{currency.symbol}{grouped}.{fraction}"


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", quantize(self.amount))

    @classmethod
    def zero(cls, currency: Currency) -> Money:
        return cls(Decimal(0), currency)

    def _check(self, other: Money) -> None:
        if self.currency is not other.currency:
            raise CurrencyMismatchError(
                f"Cannot combine {self.currency} and {other.currency}; convert with FxRates first"
            )

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Decimal | int) -> Money:
        return Money(self.amount * Decimal(factor), self.currency)

    __rmul__ = __mul__

    def __lt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._check(other)
        return self.amount <= other.amount

    def __str__(self) -> str:
        return format_amount(self.amount, self.currency)
