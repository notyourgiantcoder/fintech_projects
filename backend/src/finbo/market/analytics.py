"""Deterministic statistics over price history. Agents quote these; they never compute them."""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal

from ..core import quantize
from .models import Bar, HistoryStats

TRADING_DAYS = 252


def history_stats(symbol: str, period: str, bars: Sequence[Bar]) -> HistoryStats:
    closes = [b for b in bars if b.close > 0]
    if len(closes) < 2:
        raise ValueError(f"Not enough price history for {symbol} over {period}")

    first, last = closes[0], closes[-1]
    values = [float(b.close) for b in closes]

    daily = [values[i] / values[i - 1] - 1 for i in range(1, len(values))]
    volatility = None
    if len(daily) >= 5:
        mean = sum(daily) / len(daily)
        variance = sum((r - mean) ** 2 for r in daily) / (len(daily) - 1)
        volatility = quantize(Decimal(str(math.sqrt(variance) * math.sqrt(TRADING_DAYS) * 100)))

    peak = values[0]
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)

    return HistoryStats(
        symbol=symbol,
        period=period,
        start=first.day,
        end=last.day,
        start_close=quantize(first.close),
        end_close=quantize(last.close),
        return_pct=quantize((last.close / first.close - 1) * 100),
        annualised_volatility_pct=volatility,
        max_drawdown_pct=quantize(Decimal(str(worst * 100))),
        high=quantize(max(b.close for b in closes)),
        low=quantize(min(b.close for b in closes)),
    )
