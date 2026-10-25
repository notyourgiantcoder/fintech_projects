import json
from decimal import Decimal

import pytest

from finbo.core import quantize
from finbo.session import FinanceSession
from finbo.tools import build_personal_tools


@pytest.fixture
def session() -> FinanceSession:
    return FinanceSession.sample("in")


@pytest.fixture
def tools(session):
    return build_personal_tools(session)


def test_tool_names_and_schemas(tools):
    assert set(tools) == {
        "get_financial_profile",
        "analyze_spending",
        "plan_emergency_fund",
        "compare_debt_strategies",
        "split_surplus",
    }
    extra = tools["compare_debt_strategies"].parameters()["properties"]["extra_monthly_payment"]
    assert extra["minimum"] == 0 and "description" in extra


def test_outputs_are_json_serialisable(tools):
    for name in ("get_financial_profile", "analyze_spending", "plan_emergency_fund"):
        json.dumps(tools[name].func())
    json.dumps(tools["compare_debt_strategies"].func())
    json.dumps(tools["split_surplus"].func(weights={"a": 1}))


def test_emergency_fund_default_contribution_is_stated(session, tools):
    out = tools["plan_emergency_fund"].func()
    expected = quantize(session.budget_report().avg_monthly_savings / 2)
    assert Decimal(out["plan"]["monthly_contribution"]) == expected
    assert any("50%" in a for a in out["assumptions"])


def test_emergency_fund_explicit_contribution(tools):
    out = tools["plan_emergency_fund"].func(monthly_contribution=10000)
    assert out["plan"]["monthly_contribution"] == "10000.00"
    assert not any("50%" in a for a in out["assumptions"])


def test_extra_debt_payment_lowers_interest(tools):
    base = tools["compare_debt_strategies"].func()
    extra = tools["compare_debt_strategies"].func(extra_monthly_payment=10000)
    assert Decimal(extra["monthly_budget"]) == Decimal(base["sum_of_minimums"]) + 10000
    base_interest = Decimal(base["comparison"]["avalanche"]["total_interest"])
    assert Decimal(extra["comparison"]["avalanche"]["total_interest"]) < base_interest


def test_no_debts(session):
    debt_free = FinanceSession(
        profile=session.profile.model_copy(update={"debts": []}),
        transactions=session.transactions,
    )
    out = build_personal_tools(debt_free)["compare_debt_strategies"].func()
    assert "no outstanding debts" in out["message"]


def test_split_surplus_is_exact(tools):
    out = tools["split_surplus"].func(weights={"emergency_fund": 2, "sip": 1}, amount=1000)
    assert out["allocation"] == {"emergency_fund": "666.67", "sip": "333.33"}


def test_split_surplus_reports_bad_weights(tools):
    assert "error" in tools["split_surplus"].func(weights={"a": 0})


def test_user_override_reclassifies_category(session):
    assert session.budget_report().unclassified_categories == ["Gym"]
    session.bucket_overrides["Gym"] = "wants"
    out = build_personal_tools(session)["analyze_spending"].func()
    assert out["unclassified_categories"] == []
