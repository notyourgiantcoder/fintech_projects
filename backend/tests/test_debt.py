from decimal import Decimal

import pytest

from finbo.core import (
    Currency,
    CurrencyMismatchError,
    Debt,
    InsufficientBudgetError,
    NonAmortizingError,
    compare_strategies,
    simulate_payoff,
)


def debt(name, balance, rate, minimum, currency=Currency.USD) -> Debt:
    return Debt(
        name=name,
        balance=Decimal(balance),
        annual_rate_pct=Decimal(rate),
        minimum_payment=Decimal(minimum),
        currency=currency,
    )


def test_zero_interest_is_plain_division():
    plan = simulate_payoff([debt("A", 1000, 0, 100)], Decimal(300), "avalanche")
    assert plan.months == 4  # 300 + 300 + 300 + 100
    assert plan.total_interest == 0
    assert plan.total_paid == Decimal("1000.00")


def test_matches_amortization_formula():
    # 1000 at 12% APR, 100/month -> n = -ln(1 - 0.01*1000/100) / ln(1.01) ~= 10.59 months
    plan = simulate_payoff([debt("Card", 1000, 12, 100)], Decimal(100), "avalanche")
    assert plan.months == 11
    assert abs(plan.total_interest - Decimal(59)) < 2


def test_strategies_diverge_on_order_and_cost():
    debts = [debt("Expensive", 5000, 25, 100), debt("Small", 1000, 5, 50)]
    cmp = compare_strategies(debts, Decimal(500))
    assert cmp.avalanche.target_order == ["Expensive", "Small"]
    assert cmp.snowball.target_order == ["Small", "Expensive"]
    assert cmp.avalanche.payoff_order[0].name == "Expensive"
    assert cmp.snowball.payoff_order[0].name == "Small"
    assert cmp.interest_saved_with_avalanche > 0
    assert cmp.earlier_first_win_with_snowball > 0
    assert cmp.cheapest == "avalanche"


def test_money_is_conserved(sample_profile):
    principal = sum(d.balance for d in sample_profile.debts)
    budget = sum(d.minimum_payment for d in sample_profile.debts) * Decimal("1.5")
    for strategy in ("avalanche", "snowball"):
        plan = simulate_payoff(sample_profile.debts, budget, strategy)
        assert plan.total_paid == principal + plan.total_interest
        assert sum(p.interest_paid for p in plan.payoff_order) == plan.total_interest


def test_avalanche_never_costs_more(sample_profile):
    budget = sum(d.minimum_payment for d in sample_profile.debts) + 100
    cmp = compare_strategies(sample_profile.debts, budget)
    assert cmp.avalanche.total_interest <= cmp.snowball.total_interest


def test_budget_below_minimums():
    with pytest.raises(InsufficientBudgetError):
        simulate_payoff(
            [debt("A", 1000, 10, 100), debt("B", 1000, 10, 100)], Decimal(150), "snowball"
        )


def test_interest_outpaces_payments():
    # 36% APR on 1,00,000 accrues 3,000/month; paying 2,000 never catches up.
    d = debt("Card", 100000, 36, 1000, Currency.INR)
    with pytest.raises(NonAmortizingError):
        simulate_payoff([d], Decimal(2000), "avalanche")


def test_mixed_currency_rejected():
    with pytest.raises(CurrencyMismatchError):
        simulate_payoff(
            [debt("A", 100, 0, 10), debt("B", 100, 0, 10, Currency.INR)], Decimal(50), "avalanche"
        )


def test_paid_off_debts_are_ignored():
    plan = simulate_payoff(
        [debt("Done", 0, 20, 50), debt("A", 100, 0, 50)], Decimal(50), "avalanche"
    )
    assert [p.name for p in plan.payoff_order] == ["A"]
    with pytest.raises(ValueError):
        simulate_payoff([debt("Done", 0, 20, 50)], Decimal(50), "avalanche")
