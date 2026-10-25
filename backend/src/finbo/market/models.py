from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class Quote(BaseModel):
    symbol: str
    name: str | None
    exchange: str | None
    currency: str
    price: Decimal
    previous_close: Decimal | None
    change_pct: Decimal | None
    day_low: Decimal | None
    day_high: Decimal | None
    year_low: Decimal | None
    year_high: Decimal | None
    market_cap: Decimal | None
    as_of: datetime


class Bar(BaseModel):
    day: date
    close: Decimal


class CompanyProfile(BaseModel):
    symbol: str
    name: str | None
    sector: str | None
    industry: str | None
    trailing_pe: Decimal | None
    dividend_yield_pct: Decimal | None
    market_cap: Decimal | None
    currency: str | None
    summary: str | None


class SymbolMatch(BaseModel):
    symbol: str
    name: str | None
    exchange: str | None
    kind: str | None


class HistoryStats(BaseModel):
    symbol: str
    period: str
    start: date
    end: date
    start_close: Decimal
    end_close: Decimal
    return_pct: Decimal
    annualised_volatility_pct: Decimal | None
    max_drawdown_pct: Decimal
    high: Decimal
    low: Decimal
