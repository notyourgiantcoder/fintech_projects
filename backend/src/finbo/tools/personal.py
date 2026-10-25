"""Agent tools over the finance engine, bound to one FinanceSession.

Tools return JSON-ready dicts. Any default the tool picks on the user's behalf is
listed under "assumptions" so the agent can state it and a human can challenge it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from agent_framework import FunctionTool, tool
from pydantic import Field

from ..core import (
    InsufficientBudgetError,
    NonAmortizingError,
    allocate_by_weight,
    compare_strategies,
    plan_emergency_fund,
    quantize,
)
from ..session import FinanceSession

DEFAULT_EF_SHARE_OF_SURPLUS = Decimal("0.5")


def _dec(value: float) -> Decimal:
    return Decimal(str(value))


def build_personal_tools(session: FinanceSession) -> dict[str, FunctionTool]:
    profile = session.profile

    @tool(
        name="get_financial_profile",
        description="The user's currency, monthly income, income stability, dependents, "
        "emergency fund balance and list of debts.",
    )
    def get_financial_profile() -> dict[str, Any]:
        return profile.model_dump(mode="json")

    @tool(
        name="analyze_spending",
        description="Spending analysis from the user's transactions: monthly averages, "
        "category breakdown, 50/30/20 buckets, savings rate, and categories that still "
        "need the user to classify.",
    )
    def analyze_spending() -> dict[str, Any]:
        return session.budget_report().model_dump(mode="json")

    @tool(
        name="plan_emergency_fund",
        description="Emergency fund target, gap and months to reach it. Target months follow "
        "income stability and dependents; essentials = average monthly 'needs' spending.",
    )
    def emergency_fund(
        monthly_contribution: Annotated[
            float | None,
            Field(
                ge=0,
                description="Amount saved toward the fund each month. Omit to use 50% of "
                "the average monthly surplus.",
            ),
        ] = None,
    ) -> dict[str, Any]:
        report = session.budget_report()
        assumptions = ["Essential expenses = average monthly spending in 'needs' categories"]
        if monthly_contribution is None:
            contribution = quantize(
                max(report.avg_monthly_savings, Decimal(0)) * DEFAULT_EF_SHARE_OF_SURPLUS
            )
            assumptions.append("Monthly contribution defaults to 50% of the average surplus")
        else:
            contribution = _dec(monthly_contribution)
        plan = plan_emergency_fund(
            currency=profile.currency,
            monthly_essential_expenses=session.monthly_essentials(report),
            current_balance=profile.emergency_fund_balance,
            stability=profile.income_stability,
            dependents=profile.dependents,
            monthly_contribution=contribution,
        )
        return {"plan": plan.model_dump(mode="json"), "assumptions": assumptions}

    @tool(
        name="compare_debt_strategies",
        description="Simulate paying off all debts with the avalanche (highest rate first) and "
        "snowball (smallest balance first) methods. Budget = sum of minimum payments + extra.",
    )
    def debt_strategies(
        extra_monthly_payment: Annotated[
            float, Field(ge=0, description="Money per month on top of all minimum payments.")
        ] = 0.0,
    ) -> dict[str, Any]:
        debts = [d for d in profile.debts if d.balance > 0]
        if not debts:
            return {"message": "The user has no outstanding debts."}
        minimums = sum((d.minimum_payment for d in debts), Decimal(0))
        budget = minimums + _dec(extra_monthly_payment)
        try:
            comparison = compare_strategies(debts, budget)
        except (InsufficientBudgetError, NonAmortizingError) as e:
            return {"error": str(e)}
        return {
            "monthly_budget": str(quantize(budget)),
            "sum_of_minimums": str(minimums),
            "comparison": comparison.model_dump(mode="json"),
            "assumptions": [
                "Interest rates and minimum payments stay constant",
                "No new borrowing during the payoff period",
            ],
        }

    @tool(
        name="split_surplus",
        description="Split an amount across goals in proportion to weights; parts always add "
        "up exactly to the amount.",
    )
    def split_surplus(
        weights: Annotated[
            dict[str, float],
            Field(description="Goal name -> relative weight, e.g. {'emergency_fund': 2, 'sip': 1}"),
        ],
        amount: Annotated[
            float | None,
            Field(ge=0, description="Amount to split. Omit to use the average monthly surplus."),
        ] = None,
    ) -> dict[str, Any]:
        assumptions = []
        if amount is None:
            total = max(session.budget_report().avg_monthly_savings, Decimal(0))
            assumptions.append("Amount = average monthly surplus from the spending analysis")
        else:
            total = _dec(amount)
        try:
            parts = allocate_by_weight(total, {k: _dec(v) for k, v in weights.items()})
        except ValueError as e:
            return {"error": str(e)}
        return {
            "amount": str(quantize(total)),
            "allocation": {k: str(v) for k, v in parts.items()},
            "assumptions": assumptions,
        }

    tools = [
        get_financial_profile,
        analyze_spending,
        emergency_fund,
        debt_strategies,
        split_surplus,
    ]
    return {t.name: t for t in tools}
