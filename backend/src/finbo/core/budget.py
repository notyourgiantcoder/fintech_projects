"""Budget analysis: category breakdown, monthly trend and 50/30/20 comparison."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from .models import Transaction
from .money import Currency, CurrencyMismatchError, quantize

Bucket = Literal["needs", "wants", "savings", "unclassified"]

# 50/30/20 rule targets as % of income.
BUCKET_TARGETS_PCT: dict[Bucket, Decimal] = {
    "needs": Decimal(50),
    "wants": Decimal(30),
    "savings": Decimal(20),
}

# Lower-cased category -> bucket. Anything not listed is "unclassified" and is
# surfaced to the user to classify rather than guessed.
DEFAULT_BUCKETS: dict[str, Bucket] = {
    **dict.fromkeys(
        [
            "housing",
            "rent",
            "utilities",
            "electricity",
            "groceries",
            "food",
            "transportation",
            "transport",
            "fuel",
            "insurance",
            "healthcare",
            "medical",
            "education",
            "emi",
            "loan",
            "debt payments",
            "childcare",
            "phone",
            "internet",
        ],
        "needs",
    ),
    **dict.fromkeys(
        [
            "dining",
            "dining out",
            "restaurants",
            "entertainment",
            "shopping",
            "travel",
            "subscriptions",
            "personal care",
            "gifts",
            "hobbies",
            "food delivery",
        ],
        "wants",
    ),
    **dict.fromkeys(
        ["savings", "investments", "sip", "mutual funds", "ppf", "401k", "ira", "stocks"],
        "savings",
    ),
}


class CategoryShare(BaseModel):
    category: str
    bucket: Bucket
    total: Decimal
    monthly_avg: Decimal
    share_pct: Decimal  # % of total outflow


class BucketShare(BaseModel):
    bucket: Bucket
    monthly_avg: Decimal
    pct_of_income: Decimal | None
    target_pct: Decimal | None


class MonthTotal(BaseModel):
    month: str  # YYYY-MM
    total: Decimal


class BudgetReport(BaseModel):
    currency: Currency
    period_start: date
    period_end: date
    months: int
    monthly_income: Decimal
    total_outflow: Decimal
    avg_monthly_spending: Decimal  # needs + wants + unclassified (excludes savings/investments)
    avg_monthly_savings: Decimal  # income - spending (includes explicit investments)
    savings_rate_pct: Decimal | None
    categories: list[CategoryShare]
    buckets: list[BucketShare]
    monthly_totals: list[MonthTotal]
    unclassified_categories: list[str]


def _pct(part: Decimal, whole: Decimal) -> Decimal | None:
    return quantize(part / whole * 100) if whole else None


def analyze_budget(
    transactions: Sequence[Transaction],
    monthly_income: Decimal,
    *,
    buckets: Mapping[str, Bucket] | None = None,
) -> BudgetReport:
    """Summarise spending. Monthly averages divide by the number of distinct months present."""
    if not transactions:
        raise ValueError("No transactions to analyse")
    currency = transactions[0].currency
    if any(t.currency is not currency for t in transactions):
        raise CurrencyMismatchError("All transactions must share one currency; convert first")

    bucket_map = {k.lower(): v for k, v in (buckets or DEFAULT_BUCKETS).items()}
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    by_month: dict[str, Decimal] = defaultdict(Decimal)
    for t in transactions:
        by_category[t.category] += t.amount
        by_month[t.date.strftime("%Y-%m")] += t.amount

    months = len(by_month)
    total_outflow = sum(by_category.values(), Decimal(0))
    income = quantize(monthly_income)

    categories = []
    bucket_totals: dict[Bucket, Decimal] = defaultdict(Decimal)
    for name, total in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True):
        bucket = bucket_map.get(name.lower(), "unclassified")
        bucket_totals[bucket] += total
        categories.append(
            CategoryShare(
                category=name,
                bucket=bucket,
                total=quantize(total),
                monthly_avg=quantize(total / months),
                share_pct=_pct(total, total_outflow) or Decimal(0),
            )
        )

    spending_total = total_outflow - bucket_totals["savings"]
    avg_spending = quantize(spending_total / months)
    avg_savings = income - avg_spending

    bucket_rows = []
    for bucket in ("needs", "wants", "savings", "unclassified"):
        if bucket == "savings":
            monthly = avg_savings  # explicit investments + leftover surplus
        else:
            monthly = quantize(bucket_totals[bucket] / months)
            if bucket == "unclassified" and not monthly:
                continue
        bucket_rows.append(
            BucketShare(
                bucket=bucket,
                monthly_avg=monthly,
                pct_of_income=_pct(monthly, income),
                target_pct=BUCKET_TARGETS_PCT.get(bucket),
            )
        )

    dates = [t.date for t in transactions]
    return BudgetReport(
        currency=currency,
        period_start=min(dates),
        period_end=max(dates),
        months=months,
        monthly_income=income,
        total_outflow=quantize(total_outflow),
        avg_monthly_spending=avg_spending,
        avg_monthly_savings=avg_savings,
        savings_rate_pct=_pct(avg_savings, income),
        categories=categories,
        buckets=bucket_rows,
        monthly_totals=[
            MonthTotal(month=m, total=quantize(v)) for m, v in sorted(by_month.items())
        ],
        unclassified_categories=[c.category for c in categories if c.bucket == "unclassified"],
    )
