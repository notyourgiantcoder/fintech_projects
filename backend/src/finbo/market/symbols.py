"""Ticker normalisation across NSE, BSE and US exchanges."""

from __future__ import annotations

import re

from ..session import Market

# An optional leading ^ marks an index (^NSEI, ^GSPC).
_VALID = re.compile(r"^\^?[A-Z0-9][A-Z0-9.&=\-]{0,19}$")
_INDIAN_SUFFIXES = (".NS", ".BO")


class InvalidSymbolError(ValueError):
    pass


def normalize_symbol(raw: str, market: Market) -> str:
    """'reliance' (India) -> 'RELIANCE.NS'; 'aapl' -> 'AAPL'; '500325.bo' -> '500325.BO'.

    Indian tickers without an exchange suffix default to NSE. Index (^NSEI) and currency
    (USDINR=X) symbols pass through unchanged.
    """
    symbol = raw.strip().upper().replace(" ", "")
    if not _VALID.match(symbol):
        raise InvalidSymbolError(f"{raw!r} isn't a valid ticker symbol.")
    if (
        market == "in"
        and not symbol.endswith(_INDIAN_SUFFIXES)
        and not symbol.startswith("^")
        and "=" not in symbol
        and "." not in symbol
    ):
        symbol += ".NS"
    return symbol
