"""Emergency-fund sizing and surplus allocation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from pydantic import BaseModel

from .models import IncomeStability
from .money import Currency, quantize

BASE_MONTHS: dict[IncomeStability, int] = {"stable": 3, "variable": 6}
MAX_MONTHS = 12


class EmergencyFundPlan(BaseModel):
    currency: Currency
    target_months: int
    monthly_essential_expenses: Decimal
    target_amount: Decimal
    current_balance: Decimal
    gap: Decimal
    coverage_months: Decimal | None
    monthly_contribution: Decimal
    months_to_target: int | None  # None when the gap can't close at this contribution
    is_funded: bool


def emergency_fund_months(stability: IncomeStability, dependents: int) -> int:
    """3 months (stable) or 6 (variable) income, +1 per dependent, capped at 12."""
    return min(BASE_MONTHS[stability] + dependents, MAX_MONTHS)


def plan_emergency_fund(
    *,
    currency: Currency,
    monthly_essential_expenses: Decimal,
    current_balance: Decimal,
    stability: IncomeStability = "stable",
    dependents: int = 0,
    monthly_contribution: Decimal = Decimal(0),
) -> EmergencyFundPlan:
    if monthly_essential_expenses < 0 or current_balance < 0 or monthly_contribution < 0:
        raise ValueError("Amounts must be non-negative")

    essentials = quantize(monthly_essential_expenses)
    months = emergency_fund_months(stability, dependents)
    target = quantize(essentials * months)
    balance = quantize(current_balance)
    gap = max(target - balance, Decimal(0))
    contribution = quantize(monthly_contribution)

    if gap == 0:
        months_to_target: int | None = 0
    elif contribution > 0:
        months_to_target = int((gap / contribution).to_integral_value(rounding=ROUND_CEILING))
    else:
        months_to_target = None

    return EmergencyFundPlan(
        currency=currency,
        target_months=months,
        monthly_essential_expenses=essentials,
        target_amount=target,
        current_balance=balance,
        gap=quantize(gap),
        coverage_months=(balance / essentials).quantize(Decimal("0.1")) if essentials else None,
        monthly_contribution=contribution,
        months_to_target=months_to_target,
        is_funded=gap == 0,
    )


def allocate_by_weight(total: Decimal, weights: Mapping[str, Decimal | int]) -> dict[str, Decimal]:
    """Split `total` across goals proportionally to `weights`.

    Uses the largest-remainder method on whole cents so the parts always sum to
    exactly `total` (no rounding drift for the UI or the guardrail check to flag).
    """
    if total < 0:
        raise ValueError("total must be non-negative")
    w = {k: Decimal(v) for k, v in weights.items()}
    if not w or any(v < 0 for v in w.values()) or sum(w.values()) == 0:
        raise ValueError("weights must be non-negative and not all zero")

    total_cents = int(quantize(total) * 100)
    weight_sum = sum(w.values())
    exact = {k: total_cents * v / weight_sum for k, v in w.items()}
    floors = {k: int(x.to_integral_value(rounding=ROUND_FLOOR)) for k, x in exact.items()}
    leftover = total_cents - sum(floors.values())
    # Hand out remaining cents to the largest fractional parts (stable on ties by input order).
    order = sorted(w, key=lambda k: exact[k] - floors[k], reverse=True)
    for k in order[:leftover]:
        floors[k] += 1
    return {k: quantize(Decimal(c) / 100) for k, c in floors.items()}
