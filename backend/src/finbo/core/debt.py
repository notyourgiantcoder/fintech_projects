"""Debt payoff simulation: avalanche vs snowball.

Month-by-month simulation with a fixed total monthly budget:
  1. interest accrues on every open balance (APR / 12, rounded to cents),
  2. every open debt receives its minimum payment,
  3. whatever is left goes to the priority debt, cascading down the list.
Because the budget stays constant, minimums freed by cleared debts roll forward
automatically, which is what makes both strategies "snowball" in effect.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from .models import Debt
from .money import Currency, CurrencyMismatchError, quantize

Strategy = Literal["avalanche", "snowball"]
MAX_MONTHS = 600  # 50 years


class InsufficientBudgetError(ValueError):
    pass


class NonAmortizingError(ValueError):
    """The budget never pays the debts down (interest >= payments)."""


class DebtPayoff(BaseModel):
    name: str
    month_paid_off: int
    interest_paid: Decimal


class PayoffPlan(BaseModel):
    strategy: Strategy
    currency: Currency
    monthly_budget: Decimal
    months: int
    first_payoff_month: int
    total_interest: Decimal
    total_paid: Decimal
    # Which debt receives the extra money first (the strategy's priority list).
    target_order: list[str]
    # When each debt actually clears; can differ from target_order because a debt
    # with a large minimum (e.g. an EMI) may clear on minimums alone.
    payoff_order: list[DebtPayoff]


class StrategyComparison(BaseModel):
    avalanche: PayoffPlan
    snowball: PayoffPlan
    interest_saved_with_avalanche: Decimal
    months_saved_with_avalanche: int
    earlier_first_win_with_snowball: int  # months sooner the first debt is cleared
    cheapest: Strategy


def _priority(debts: Sequence[Debt], strategy: Strategy) -> list[int]:
    idx = range(len(debts))
    if strategy == "avalanche":
        # Highest rate first; smaller balance breaks ties.
        return sorted(idx, key=lambda i: (-debts[i].annual_rate_pct, debts[i].balance, i))
    # Smallest balance first; higher rate breaks ties.
    return sorted(idx, key=lambda i: (debts[i].balance, -debts[i].annual_rate_pct, i))


def simulate_payoff(
    debts: Sequence[Debt], monthly_budget: Decimal, strategy: Strategy
) -> PayoffPlan:
    open_debts = [d for d in debts if d.balance > 0]
    if not open_debts:
        raise ValueError("No outstanding debts to simulate")
    currency = open_debts[0].currency
    if any(d.currency is not currency for d in open_debts):
        raise CurrencyMismatchError("All debts must share one currency; convert first")

    budget = quantize(monthly_budget)
    required = sum((d.minimum_payment for d in open_debts), Decimal(0))
    if budget < required:
        raise InsufficientBudgetError(
            f"Monthly budget {budget} is below the sum of minimum payments {required}"
        )

    balances = [d.balance for d in open_debts]
    interest = [Decimal(0)] * len(open_debts)
    paid_off_month: dict[int, int] = {}
    order = _priority(open_debts, strategy)
    total_paid = Decimal(0)
    month = 0

    while len(paid_off_month) < len(open_debts):
        month += 1
        if month > MAX_MONTHS:
            raise NonAmortizingError(f"Debts not repaid within {MAX_MONTHS} months at this budget")

        month_interest = Decimal(0)
        for i, d in enumerate(open_debts):
            if balances[i] > 0:
                charge = quantize(balances[i] * d.monthly_rate)
                balances[i] += charge
                interest[i] += charge
                month_interest += charge
        if month == 1 and month_interest >= budget:
            raise NonAmortizingError("Monthly interest exceeds the budget; balances would grow")

        available = budget
        for i in order:
            if balances[i] > 0:
                pay = min(open_debts[i].minimum_payment, balances[i])
                balances[i] -= pay
                available -= pay
        for i in order:
            if available <= 0:
                break
            if balances[i] > 0:
                pay = min(available, balances[i])
                balances[i] -= pay
                available -= pay

        total_paid += budget - available
        for i in order:
            if balances[i] == 0 and i not in paid_off_month:
                paid_off_month[i] = month

    payoff_order = [
        DebtPayoff(
            name=open_debts[i].name,
            month_paid_off=m,
            interest_paid=quantize(interest[i]),
        )
        for i, m in sorted(paid_off_month.items(), key=lambda kv: (kv[1], order.index(kv[0])))
    ]
    return PayoffPlan(
        strategy=strategy,
        currency=currency,
        monthly_budget=budget,
        months=month,
        first_payoff_month=min(paid_off_month.values()),
        total_interest=quantize(sum(interest, Decimal(0))),
        total_paid=quantize(total_paid),
        target_order=[open_debts[i].name for i in order],
        payoff_order=payoff_order,
    )


def compare_strategies(debts: Sequence[Debt], monthly_budget: Decimal) -> StrategyComparison:
    avalanche = simulate_payoff(debts, monthly_budget, "avalanche")
    snowball = simulate_payoff(debts, monthly_budget, "snowball")
    saved = snowball.total_interest - avalanche.total_interest
    return StrategyComparison(
        avalanche=avalanche,
        snowball=snowball,
        interest_saved_with_avalanche=saved,
        months_saved_with_avalanche=snowball.months - avalanche.months,
        earlier_first_win_with_snowball=avalanche.first_payoff_month - snowball.first_payoff_month,
        cheapest="snowball" if saved < 0 else "avalanche",
    )
