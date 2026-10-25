from decimal import Decimal

import pytest

from finbo.core import Currency, allocate_by_weight, plan_emergency_fund
from finbo.core.savings import emergency_fund_months


def test_emergency_months_rule():
    assert emergency_fund_months("stable", 0) == 3
    assert emergency_fund_months("variable", 0) == 6
    assert emergency_fund_months("stable", 2) == 5
    assert emergency_fund_months("variable", 10) == 12  # capped


def test_plan_with_gap():
    plan = plan_emergency_fund(
        currency=Currency.INR,
        monthly_essential_expenses=Decimal(50000),
        current_balance=Decimal(60000),
        dependents=1,
        monthly_contribution=Decimal(15000),
    )
    assert plan.target_months == 4
    assert plan.target_amount == Decimal("200000.00")
    assert plan.gap == Decimal("140000.00")
    assert plan.months_to_target == 10  # ceil(140000 / 15000)
    assert plan.coverage_months == Decimal("1.2")
    assert not plan.is_funded


def test_plan_already_funded():
    plan = plan_emergency_fund(
        currency=Currency.USD,
        monthly_essential_expenses=Decimal(1000),
        current_balance=Decimal(5000),
    )
    assert plan.is_funded and plan.gap == 0 and plan.months_to_target == 0


def test_plan_without_contribution_never_reaches_target():
    plan = plan_emergency_fund(
        currency=Currency.USD,
        monthly_essential_expenses=Decimal(1000),
        current_balance=Decimal(0),
    )
    assert plan.months_to_target is None


def test_allocate_by_weight_is_exact():
    parts = allocate_by_weight(Decimal(100), {"a": 1, "b": 1, "c": 1})
    assert sum(parts.values()) == Decimal("100.00")
    assert sorted(parts.values()) == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]


@pytest.mark.parametrize("total", ["0", "0.01", "999.99", "123456.78"])
def test_allocate_by_weight_never_drifts(total):
    parts = allocate_by_weight(
        Decimal(total), {"ef": 5, "debt": 3, "sip": 2, "fun": Decimal("0.7")}
    )
    assert sum(parts.values()) == Decimal(total)


@pytest.mark.parametrize("weights", [{}, {"a": 0}, {"a": -1, "b": 2}])
def test_allocate_by_weight_rejects_bad_weights(weights):
    with pytest.raises(ValueError):
        allocate_by_weight(Decimal(10), weights)
