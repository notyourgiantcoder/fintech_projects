"""A user's financial data for one conversation.

Agents never receive raw figures in their prompts to copy around; tools read from
this session, so the LLM cannot alter the underlying data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal

from .core import FinancialProfile, Transaction, analyze_budget, parse_transactions_csv
from .core.budget import DEFAULT_BUCKETS, Bucket, BudgetReport

Market = Literal["in", "us"]

# The repo's data/samples in development; containers point FINBO_SAMPLES_DIR at
# their copy, since an installed package no longer sits inside the repo.
_REPO_SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"


def samples_dir() -> Path:
    return Path(os.getenv("FINBO_SAMPLES_DIR") or _REPO_SAMPLES)


@dataclass
class FinanceSession:
    profile: FinancialProfile
    transactions: list[Transaction]
    # Category -> bucket decisions made by the user (human-in-the-loop overrides).
    bucket_overrides: dict[str, Bucket] = field(default_factory=dict)

    @classmethod
    def from_files(cls, profile_path: Path, transactions_path: Path) -> FinanceSession:
        profile = FinancialProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))
        result = parse_transactions_csv(transactions_path, profile.currency)
        if result.errors:
            details = "; ".join(f"line {e.line} {e.column}: {e.message}" for e in result.errors)
            raise ValueError(f"{transactions_path.name} has invalid rows: {details}")
        return cls(profile=profile, transactions=result.transactions)

    @classmethod
    def sample(cls, market: Market) -> FinanceSession:
        return cls.from_files(
            samples_dir() / f"profile_{market}.json", samples_dir() / f"transactions_{market}.csv"
        )

    def budget_report(self) -> BudgetReport:
        buckets = {**DEFAULT_BUCKETS, **{k.lower(): v for k, v in self.bucket_overrides.items()}}
        return analyze_budget(self.transactions, self.profile.monthly_income, buckets=buckets)

    def monthly_essentials(self, report: BudgetReport | None = None) -> Decimal:
        report = report or self.budget_report()
        return next(b.monthly_avg for b in report.buckets if b.bucket == "needs")
