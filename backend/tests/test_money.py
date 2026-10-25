from datetime import date
from decimal import Decimal

import pytest

from finbo.core import (
    Currency,
    CurrencyMismatchError,
    FxRates,
    MissingRateError,
    Money,
    format_amount,
    quantize,
)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("999", "₹999.00"),
        ("1000", "₹1,000.00"),
        ("100000", "₹1,00,000.00"),
        ("1234567.5", "₹12,34,567.50"),
        ("-25000", "-₹25,000.00"),
    ],
)
def test_inr_uses_indian_grouping(amount, expected):
    assert format_amount(Decimal(amount), Currency.INR) == expected


def test_usd_uses_western_grouping():
    assert format_amount(Decimal("1234567.5"), Currency.USD) == "$1,234,567.50"


def test_quantize_rounds_half_up():
    assert quantize(Decimal("0.005")) == Decimal("0.01")
    assert quantize(Decimal("2.345")) == Decimal("2.35")


def test_money_refuses_mixed_currency_arithmetic():
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal(1), Currency.INR) + Money(Decimal(1), Currency.USD)


def test_money_arithmetic_and_display():
    total = Money(Decimal("10.10"), Currency.USD) + Money(Decimal("0.20"), Currency.USD)
    assert total == Money(Decimal("10.30"), Currency.USD)
    assert str(total * 2) == "$20.60"


def test_fx_convert_both_directions():
    fx = FxRates.from_pair(Currency.USD, Currency.INR, "83.25", as_of=date(2026, 10, 24))
    assert fx.convert(Money(Decimal(100), Currency.USD), Currency.INR).amount == Decimal("8325.00")
    assert fx.convert(Money(Decimal("8325"), Currency.INR), Currency.USD).amount == Decimal(
        "100.00"
    )
    assert fx.rate(Currency.INR, Currency.INR) == 1


def test_fx_missing_rate():
    with pytest.raises(MissingRateError):
        FxRates(as_of=date(2026, 10, 24)).rate(Currency.USD, Currency.INR)
