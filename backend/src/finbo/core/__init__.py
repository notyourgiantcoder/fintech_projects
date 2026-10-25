"""Deterministic finance engine.

Agents call these functions as tools; the LLM explains results but never does the
arithmetic itself. Everything here is pure, Decimal-based and unit-tested.
"""

from .budget import BudgetReport, analyze_budget
from .debt import (
    InsufficientBudgetError,
    NonAmortizingError,
    PayoffPlan,
    StrategyComparison,
    compare_strategies,
    simulate_payoff,
)
from .fx import FxRates, MissingRateError
from .ingest import CsvSchemaError, IngestResult, RowError, parse_transactions_csv
from .models import Debt, FinancialProfile, Transaction
from .money import Currency, CurrencyMismatchError, Money, format_amount, quantize
from .savings import EmergencyFundPlan, allocate_by_weight, plan_emergency_fund

__all__ = [
    "BudgetReport",
    "CsvSchemaError",
    "Currency",
    "CurrencyMismatchError",
    "Debt",
    "EmergencyFundPlan",
    "FinancialProfile",
    "FxRates",
    "IngestResult",
    "InsufficientBudgetError",
    "MissingRateError",
    "Money",
    "NonAmortizingError",
    "PayoffPlan",
    "RowError",
    "StrategyComparison",
    "Transaction",
    "allocate_by_weight",
    "analyze_budget",
    "compare_strategies",
    "format_amount",
    "parse_transactions_csv",
    "plan_emergency_fund",
    "quantize",
    "simulate_payoff",
]
