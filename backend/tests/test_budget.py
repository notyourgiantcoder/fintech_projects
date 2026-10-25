from datetime import date
from decimal import Decimal

import pytest

from finbo.core import (
    Currency,
    CurrencyMismatchError,
    Transaction,
    analyze_budget,
    parse_transactions_csv,
)


def tx(day: str, category: str, amount: str, currency=Currency.USD) -> Transaction:
    return Transaction(
        date=date.fromisoformat(day), category=category, amount=Decimal(amount), currency=currency
    )


@pytest.fixture
def two_months():
    return [
        tx("2026-01-01", "Rent", "400"),
        tx("2026-01-10", "Dining", "100"),
        tx("2026-02-01", "Rent", "400"),
        tx("2026-02-05", "Investments", "100"),
        tx("2026-02-09", "Gym", "50"),
    ]


def test_hand_computed_report(two_months):
    r = analyze_budget(two_months, Decimal(1000))
    assert r.months == 2
    assert r.total_outflow == Decimal("1050.00")
    # Spending excludes the investment: (400+100+400+50) / 2
    assert r.avg_monthly_spending == Decimal("475.00")
    assert r.avg_monthly_savings == Decimal("525.00")
    assert r.savings_rate_pct == Decimal("52.50")

    buckets = {b.bucket: b for b in r.buckets}
    assert buckets["needs"].monthly_avg == Decimal("400.00")
    assert buckets["needs"].pct_of_income == Decimal("40.00")
    assert buckets["wants"].pct_of_income == Decimal("5.00")
    assert buckets["unclassified"].monthly_avg == Decimal("25.00")
    assert buckets["savings"].pct_of_income == Decimal("52.50")

    assert r.categories[0].category == "Rent"
    assert r.categories[0].share_pct == Decimal("76.19")
    assert r.unclassified_categories == ["Gym"]
    assert [m.month for m in r.monthly_totals] == ["2026-01", "2026-02"]


def test_shares_sum_to_100(two_months):
    r = analyze_budget(two_months, Decimal(1000))
    assert abs(sum(c.share_pct for c in r.categories) - 100) <= Decimal("0.05")


def test_custom_bucket_mapping(two_months):
    r = analyze_budget(two_months, Decimal(1000), buckets={"gym": "wants", "rent": "needs"})
    assert "Gym" not in r.unclassified_categories


def test_mixed_currency_rejected():
    with pytest.raises(CurrencyMismatchError):
        analyze_budget(
            [tx("2026-01-01", "Rent", "1"), tx("2026-01-02", "Rent", "1", Currency.INR)],
            Decimal(100),
        )


def test_zero_income_has_no_rates(two_months):
    assert analyze_budget(two_months, Decimal(0)).savings_rate_pct is None


def test_empty_rejected():
    with pytest.raises(ValueError):
        analyze_budget([], Decimal(1000))


def test_india_sample_flags_gym_for_review(samples_dir):
    txs = parse_transactions_csv(samples_dir / "transactions_in.csv", Currency.INR).transactions
    r = analyze_budget(txs, Decimal(95000))
    assert r.months == 3
    assert r.currency is Currency.INR
    assert r.unclassified_categories == ["Gym"]
