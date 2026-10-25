"""Domain models shared by the engine, the agents (as tool I/O) and the API."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .money import Currency, quantize


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Transaction(_Model):
    date: dt.date
    category: str = Field(min_length=1)
    # Positive = money spent. Refunds/credits are negative.
    amount: Decimal
    currency: Currency
    description: str = ""

    @field_validator("amount")
    @classmethod
    def _round(cls, v: Decimal) -> Decimal:
        return quantize(v)


class Debt(_Model):
    name: str = Field(min_length=1)
    balance: Decimal = Field(ge=0)
    # Annual percentage rate, e.g. 36 means 36% APR (typical Indian credit card).
    annual_rate_pct: Decimal = Field(ge=0, le=100)
    minimum_payment: Decimal = Field(gt=0)
    currency: Currency

    @field_validator("balance", "minimum_payment")
    @classmethod
    def _round(cls, v: Decimal) -> Decimal:
        return quantize(v)

    @property
    def monthly_rate(self) -> Decimal:
        return self.annual_rate_pct / Decimal(1200)


IncomeStability = Literal["stable", "variable"]


class FinancialProfile(_Model):
    currency: Currency
    monthly_income: Decimal = Field(ge=0)
    income_stability: IncomeStability = "stable"
    dependents: int = Field(default=0, ge=0)
    emergency_fund_balance: Decimal = Field(default=Decimal(0), ge=0)
    debts: list[Debt] = Field(default_factory=list)

    @field_validator("debts")
    @classmethod
    def _same_currency(cls, debts: list[Debt], info) -> list[Debt]:
        currency = info.data.get("currency")
        for d in debts:
            if currency is not None and d.currency is not currency:
                raise ValueError(f"Debt '{d.name}' is in {d.currency}, profile is in {currency}")
        return debts
