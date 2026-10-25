"""Turn what a user typed into a symbol that actually trades.

Bare tickers are tried on the user's home market first, then the other one, so an Indian
user typing AAPL reaches Apple and a US user typing RELIANCE reaches RELIANCE.NS.
"""

from __future__ import annotations

from ..session import Market
from .provider import MarketDataError, MarketDataProvider
from .symbols import normalize_symbol

_OTHER: dict[Market, Market] = {"in": "us", "us": "in"}


def candidates(raw: str, market: Market) -> list[str]:
    first = normalize_symbol(raw, market)
    second = normalize_symbol(raw, _OTHER[market])
    return [first] if first == second else [first, second]


def resolve_symbol(raw: str, market: Market, provider: MarketDataProvider) -> str:
    """The first candidate with a live quote. Raises MarketDataError if none trade."""
    tried = candidates(raw, market)
    for symbol in tried:
        try:
            provider.quote(symbol)
            return symbol
        except MarketDataError:
            continue
    raise MarketDataError(
        f"Couldn’t find a listed security for {raw!r} (tried {', '.join(tried)})."
    )
