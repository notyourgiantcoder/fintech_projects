"""Foreign-exchange conversion between supported currencies.

Phase 1 uses static rates supplied by the caller. A live provider (e.g. yfinance
`USDINR=X`) will plug in later behind the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .money import Currency, Money


class MissingRateError(LookupError):
    pass


@dataclass
class FxRates:
    as_of: date
    _rates: dict[tuple[Currency, Currency], Decimal] = field(default_factory=dict)

    @classmethod
    def from_pair(
        cls, base: Currency, quote: Currency, rate: Decimal | str, as_of: date
    ) -> FxRates:
        """`rate` = units of `quote` per 1 `base`, e.g. USD->INR 83.25."""
        fx = cls(as_of=as_of)
        fx.set_rate(base, quote, Decimal(rate))
        return fx

    def set_rate(self, base: Currency, quote: Currency, rate: Decimal) -> None:
        if rate <= 0:
            raise ValueError("FX rate must be positive")
        self._rates[(base, quote)] = rate
        self._rates[(quote, base)] = Decimal(1) / rate

    def rate(self, base: Currency, quote: Currency) -> Decimal:
        if base is quote:
            return Decimal(1)
        try:
            return self._rates[(base, quote)]
        except KeyError:
            raise MissingRateError(f"No FX rate for {base}->{quote}") from None

    def convert(self, money: Money, to: Currency) -> Money:
        return Money(money.amount * self.rate(money.currency, to), to)
