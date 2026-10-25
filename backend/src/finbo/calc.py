"""Every figure the app shows, computed by the same tools the agents call."""

from __future__ import annotations

from typing import Any

from .session import FinanceSession, Market
from .tools import build_personal_tools


def calculations(
    market: Market,
    finance: FinanceSession,
    extra_debt_payment: float = 0.0,
    ef_contribution: float | None = None,
) -> dict[str, Any]:
    tools = build_personal_tools(finance)
    return {
        "market": market,
        "currency": finance.profile.currency,
        "profile": tools["get_financial_profile"].func(),
        "spending": tools["analyze_spending"].func(),
        "emergency_fund": tools["plan_emergency_fund"].func(monthly_contribution=ef_contribution),
        "debt": tools["compare_debt_strategies"].func(extra_monthly_payment=extra_debt_payment),
        "extra_debt_payment": extra_debt_payment,
        "overrides": finance.bucket_overrides,
    }
