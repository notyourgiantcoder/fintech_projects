"""Market data providers. Yahoo Finance (via yfinance) is free and needs no key, but it is
unofficial and can change without notice, so everything goes through this interface."""

from __future__ import annotations

import math
import warnings
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

from .models import Bar, CompanyProfile, Quote, SymbolMatch

Period = Literal["1mo", "3mo", "6mo", "1y", "5y"]
PERIODS: tuple[Period, ...] = ("1mo", "3mo", "6mo", "1y", "5y")


class MarketDataError(RuntimeError):
    pass


class MarketDataProvider(Protocol):
    def quote(self, symbol: str) -> Quote: ...
    def history(self, symbol: str, period: Period) -> list[Bar]: ...
    def profile(self, symbol: str) -> CompanyProfile: ...
    def search(self, query: str) -> list[SymbolMatch]: ...
    def fx_rate(self, base: str, quote: str) -> Decimal: ...


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return Decimal(str(round(f, 4)))


class YahooProvider:
    def __init__(self) -> None:
        import yfinance  # imported lazily: heavy, and tests use a fake provider

        self._yf = yfinance

    def _ticker(self, symbol: str):
        return self._yf.Ticker(symbol)

    def quote(self, symbol: str) -> Quote:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t = self._ticker(symbol)
                fi = t.fast_info
                price = _dec(fi["last_price"])
                prev = _dec(fi["previous_close"])
                currency = fi["currency"]
                name = exchange = None
                try:
                    meta = t.history_metadata or {}
                    name = meta.get("longName") or meta.get("shortName")
                    exchange = meta.get("fullExchangeName") or meta.get("exchangeName")
                except Exception:
                    pass
                quote = Quote(
                    symbol=symbol,
                    name=name,
                    exchange=exchange,
                    currency=currency or "",
                    price=price,
                    previous_close=prev,
                    change_pct=_dec((price / prev - 1) * 100) if price and prev else None,
                    day_low=_dec(fi["day_low"]),
                    day_high=_dec(fi["day_high"]),
                    year_low=_dec(fi["year_low"]),
                    year_high=_dec(fi["year_high"]),
                    market_cap=_dec(getattr(fi, "market_cap", None)),
                    as_of=datetime.now(UTC),
                )
        except Exception as e:
            raise MarketDataError(f"No quote for {symbol}: {type(e).__name__}") from e
        if quote.price is None:
            raise MarketDataError(f"No quote for {symbol}")
        return quote

    def history(self, symbol: str, period: Period) -> list[Bar]:
        interval = "1wk" if period == "5y" else "1d"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                frame = self._ticker(symbol).history(
                    period=period, interval=interval, auto_adjust=True
                )
        except Exception as e:
            raise MarketDataError(f"No history for {symbol}: {type(e).__name__}") from e
        bars = [
            Bar(day=idx.date(), close=_dec(row["Close"]))
            for idx, row in frame.iterrows()
            if _dec(row["Close"]) is not None
        ]
        if not bars:
            raise MarketDataError(f"No history for {symbol}")
        return bars

    def profile(self, symbol: str) -> CompanyProfile:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                info = self._ticker(symbol).info or {}
        except Exception as e:
            raise MarketDataError(f"No profile for {symbol}: {type(e).__name__}") from e
        summary = info.get("longBusinessSummary")
        return CompanyProfile(
            symbol=symbol,
            name=info.get("longName") or info.get("shortName"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            trailing_pe=_dec(info.get("trailingPE")),
            # Yahoo reports dividendYield already as a percentage (0.5 means 0.5%).
            dividend_yield_pct=_dec(info.get("dividendYield")),
            market_cap=_dec(info.get("marketCap")),
            currency=info.get("currency"),
            summary=summary[:600] if summary else None,
        )

    def search(self, query: str) -> list[SymbolMatch]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                quotes = self._yf.Search(query, max_results=8).quotes
        except Exception as e:
            raise MarketDataError(f"Search failed: {type(e).__name__}") from e
        return [
            SymbolMatch(
                symbol=q["symbol"],
                name=q.get("longname") or q.get("shortname"),
                exchange=q.get("exchDisp") or q.get("exchange"),
                kind=q.get("quoteType"),
            )
            for q in quotes
            if q.get("symbol")
        ]

    def fx_rate(self, base: str, quote: str) -> Decimal:
        if base == quote:
            return Decimal(1)
        rate = self.quote(f"{base}{quote}=X").price
        if not rate or rate <= 0:
            raise MarketDataError(f"No FX rate for {base}/{quote}")
        return rate


class CachedProvider:
    """Wraps any provider with short-lived caches (quotes 60s, everything else longer)."""

    def __init__(self, inner: MarketDataProvider) -> None:
        from ..net import TTLCache

        self.inner = inner
        self._quotes = TTLCache(60)
        self._history = TTLCache(900)
        self._profiles = TTLCache(6 * 3600)
        self._search = TTLCache(3600)

    def quote(self, symbol: str) -> Quote:
        return self._quotes.get_or_set(symbol, lambda: self.inner.quote(symbol))

    def history(self, symbol: str, period: Period) -> list[Bar]:
        return self._history.get_or_set(
            (symbol, period), lambda: self.inner.history(symbol, period)
        )

    def profile(self, symbol: str) -> CompanyProfile:
        return self._profiles.get_or_set(symbol, lambda: self.inner.profile(symbol))

    def search(self, query: str) -> list[SymbolMatch]:
        key = query.strip().lower()
        return self._search.get_or_set(key, lambda: self.inner.search(query))

    def fx_rate(self, base: str, quote: str) -> Decimal:
        return self._quotes.get_or_set(("fx", base, quote), lambda: self.inner.fx_rate(base, quote))


_default: MarketDataProvider | None = None


def default_provider() -> MarketDataProvider:
    global _default
    if _default is None:
        _default = CachedProvider(YahooProvider())
    return _default


def set_default_provider(provider: MarketDataProvider | None) -> None:
    """Tests swap in a fake; None restores the real one on next use."""
    global _default
    _default = provider
