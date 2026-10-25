"""Market-data tools (Yahoo Finance via yfinance; delayed, unofficial, free)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from agent_framework import FunctionTool, tool
from pydantic import Field

from ..core import Currency, FxRates, Money
from ..market import (
    InvalidSymbolError,
    MarketDataError,
    MarketDataProvider,
    Period,
    default_provider,
    history_stats,
    resolve_symbol,
)
from ..session import Market

SOURCE = "Yahoo Finance (delayed, unofficial)"

Symbol = Annotated[
    str,
    Field(
        description="Ticker. Indian symbols default to NSE (RELIANCE means RELIANCE.NS); add "
        ".BO for BSE. Examples: INFY, HDFCBANK.NS, 500325.BO, AAPL, ^NSEI, ^GSPC."
    ),
]


def build_market_tools(
    market: Market, provider: MarketDataProvider | None = None
) -> dict[str, FunctionTool]:
    def data() -> MarketDataProvider:
        return provider or default_provider()

    @tool(
        name="get_quote",
        description="Latest price, day change, day range, 52-week range and market cap.",
    )
    def get_quote(symbol: Symbol) -> dict[str, Any]:
        try:
            q = data().quote(resolve_symbol(symbol, market, data()))
        except (InvalidSymbolError, MarketDataError) as e:
            return {"error": str(e)}
        return {**q.model_dump(mode="json"), "source": SOURCE}

    @tool(
        name="get_price_history_stats",
        description="Return, annualised volatility, maximum drawdown, high and low over a "
        "period, computed from daily closes.",
    )
    def get_price_history_stats(
        symbol: Symbol,
        period: Annotated[
            Literal["1mo", "3mo", "6mo", "1y", "5y"], Field(description="Look-back window")
        ] = "1y",
    ) -> dict[str, Any]:
        try:
            s = resolve_symbol(symbol, market, data())
            stats = history_stats(s, period, data().history(s, period))
        except (InvalidSymbolError, MarketDataError, ValueError) as e:
            return {"error": str(e)}
        return {**stats.model_dump(mode="json"), "source": SOURCE}

    @tool(
        name="get_company_profile",
        description="Company name, sector, industry, trailing P/E, dividend yield, market cap "
        "and a short business summary.",
    )
    def get_company_profile(symbol: Symbol) -> dict[str, Any]:
        try:
            p = data().profile(resolve_symbol(symbol, market, data()))
        except (InvalidSymbolError, MarketDataError) as e:
            return {"error": str(e)}
        return {**p.model_dump(mode="json"), "source": SOURCE}

    @tool(
        name="search_symbols",
        description="Find ticker symbols for a company name, e.g. 'Tata Motors' or 'Apple'.",
    )
    def search_symbols(query: Annotated[str, Field(min_length=2, max_length=60)]) -> dict[str, Any]:
        try:
            matches = data().search(query)
        except MarketDataError as e:
            return {"error": str(e)}
        return {"matches": [m.model_dump() for m in matches], "source": SOURCE}

    @tool(
        name="convert_currency",
        description="Convert an amount between INR and USD at the latest exchange rate.",
    )
    def convert_currency(
        amount: Annotated[float, Field(ge=0)],
        from_currency: Literal["INR", "USD"],
        to_currency: Literal["INR", "USD"],
    ) -> dict[str, Any]:
        try:
            rate = data().fx_rate(from_currency, to_currency)
        except MarketDataError as e:
            return {"error": str(e)}
        base, quote = Currency(from_currency), Currency(to_currency)
        fx = FxRates.from_pair(base, quote, rate, as_of=date.today())
        converted = fx.convert(Money(Decimal(str(amount)), base), quote)
        return {
            "amount": str(Money(Decimal(str(amount)), base).amount),
            "from": from_currency,
            "converted": str(converted.amount),
            "to": to_currency,
            "rate": str(rate),
            "source": SOURCE,
        }

    tools = [
        get_quote,
        get_price_history_stats,
        get_company_profile,
        search_symbols,
        convert_currency,
    ]
    return {t.name: t for t in tools}


__all__ = ["Period", "build_market_tools"]
