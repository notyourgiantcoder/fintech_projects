import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fakes import FakeMarketData

from finbo.market import Bar, InvalidSymbolError, history_stats, normalize_symbol
from finbo.market.provider import CachedProvider
from finbo.tools import build_market_tools


@pytest.mark.parametrize(
    ("raw", "market", "expected"),
    [
        ("reliance", "in", "RELIANCE.NS"),
        ("infy.ns", "in", "INFY.NS"),
        ("500325.bo", "in", "500325.BO"),
        ("^nsei", "in", "^NSEI"),
        ("usdinr=x", "in", "USDINR=X"),
        ("aapl", "us", "AAPL"),
        ("brk.b", "us", "BRK.B"),
    ],
)
def test_normalize_symbol(raw, market, expected):
    assert normalize_symbol(raw, market) == expected


@pytest.mark.parametrize("raw", ["", "rm -rf /", "<script>", "A" * 30])
def test_rejects_bad_symbols(raw):
    with pytest.raises(InvalidSymbolError):
        normalize_symbol(raw, "us")


def bars(closes):
    start = date(2026, 1, 1)
    return [Bar(day=start + timedelta(days=i), close=Decimal(c)) for i, c in enumerate(closes)]


def test_history_stats_hand_computed():
    s = history_stats("X", "1mo", bars([100, 110, 99, 120, 108, 130, 125]))
    assert s.return_pct == Decimal("25.00")
    assert s.high == Decimal("130.00") and s.low == Decimal("99.00")
    # Worst fall from a running peak: 110 -> 99 is -10%, 120 -> 108 is -10%.
    assert s.max_drawdown_pct == Decimal("-10.00")
    assert s.annualised_volatility_pct is not None and s.annualised_volatility_pct > 0


def test_history_stats_needs_two_points():
    with pytest.raises(ValueError):
        history_stats("X", "1mo", bars([100]))


def test_cache_avoids_repeat_calls():
    fake = FakeMarketData()
    cached = CachedProvider(fake)
    cached.quote("AAPL")
    cached.quote("AAPL")
    assert fake.calls.count(("quote", "AAPL")) == 1


@pytest.fixture
def tools():
    return build_market_tools("in", FakeMarketData())


def test_quote_tool_normalizes_and_cites_source(tools):
    out = tools["get_quote"].func(symbol="reliance")
    assert out["symbol"] == "RELIANCE.NS" and out["price"] == "1190.00"
    assert "Yahoo Finance" in out["source"]
    json.dumps(out)


def test_tools_return_errors_instead_of_raising(tools):
    assert "error" in tools["get_quote"].func(symbol="UNKNOWN")
    assert "error" in tools["get_quote"].func(symbol="not a ticker!")
    assert "error" in tools["get_price_history_stats"].func(symbol="UNKNOWN", period="1y")


def test_history_tool(tools):
    out = tools["get_price_history_stats"].func(symbol="TCS", period="1y")
    assert out["symbol"] == "TCS.NS" and out["return_pct"] == "25.00"


def test_convert_currency_uses_engine(tools):
    out = tools["convert_currency"].func(amount=100, from_currency="USD", to_currency="INR")
    assert out == {
        "amount": "100.00",
        "from": "USD",
        "converted": "9493.00",
        "to": "INR",
        "rate": "94.93",
        "source": "Yahoo Finance (delayed, unofficial)",
    }


class USOnly(FakeMarketData):
    """Quotes only bare (US) symbols, like Yahoo does for AAPL."""

    def _check(self, symbol):
        if "." in symbol or symbol.startswith("UNKNOWN"):
            from finbo.market import MarketDataError

            raise MarketDataError(f"No quote for {symbol}")


def test_indian_user_can_reach_us_listings():
    from finbo.market import candidates, resolve_symbol

    assert candidates("aapl", "in") == ["AAPL.NS", "AAPL"]
    assert candidates("reliance.ns", "us") == ["RELIANCE.NS"]
    assert resolve_symbol("aapl", "in", USOnly()) == "AAPL"
    out = build_market_tools("in", USOnly())["get_quote"].func(symbol="aapl")
    assert out["symbol"] == "AAPL"
