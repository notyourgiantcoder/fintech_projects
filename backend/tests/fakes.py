"""A scripted chat client: lets agent wiring be tested offline, with no LLM or API key.

It reuses the framework's real function-invocation and middleware layers, so tool
calls, agent-as-tool delegation and middleware all run exactly as in production.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
    ResponseStream,
)

# Given (agent instructions, conversation so far) return the next assistant contents.
Policy = Callable[[str, Sequence[Message]], list[Content | str]]


@dataclass
class Turn:
    instructions: str
    roles: list[str]
    user_text: str


class ScriptedChatClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    def __init__(self, policy: Policy, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.policy = policy
        self.turns: list[Turn] = []

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        instructions = str(options.get("instructions") or "")
        user_text = next((m.text or "" for m in messages if str(m.role) == "user"), "")
        self.turns.append(Turn(instructions, [str(m.role) for m in messages], user_text))

        async def respond() -> ChatResponse:
            return ChatResponse(messages=Message("assistant", self.policy(instructions, messages)))

        if not stream:
            return respond()

        async def updates():
            for m in (await respond()).messages:
                yield ChatResponseUpdate(contents=list(m.contents), role=m.role)

        return ResponseStream(updates(), finalizer=ChatResponse.from_updates)


def call(name: str, call_id: str = "call-1", **arguments: Any) -> Content:
    return Content.from_function_call(call_id, name, arguments=arguments)


def tool_results(messages: Sequence[Message]) -> list[str]:
    """Function results in the latest tool message, as strings."""
    last = messages[-1]
    if str(last.role) != "tool":
        return []
    return [str(c.result) for c in last.contents if c.type == "function_result"]


# ---------- Market data ----------

from datetime import UTC, date, datetime, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

from finbo.market import Bar, CompanyProfile, MarketDataError, Quote, SymbolMatch  # noqa: E402


class FakeMarketData:
    """Fixed quotes and a short fixed price series; symbols starting UNKNOWN fail."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def _check(self, symbol: str) -> None:
        if symbol.startswith("UNKNOWN"):
            raise MarketDataError(f"No quote for {symbol}")

    def quote(self, symbol: str) -> Quote:
        self.calls.append(("quote", symbol))
        self._check(symbol)
        return Quote(
            symbol=symbol,
            name=f"{symbol} Ltd",
            exchange="NSE" if symbol.endswith(".NS") else "NasdaqGS",
            currency="INR" if symbol.endswith((".NS", ".BO")) else "USD",
            price=Decimal("1190.00"),
            previous_close=Decimal("1184.50"),
            change_pct=Decimal("0.4643"),
            day_low=Decimal("1180"),
            day_high=Decimal("1195"),
            year_low=Decimal("1100"),
            year_high=Decimal("1611.80"),
            market_cap=Decimal("16103642435650"),
            as_of=datetime(2026, 10, 25, tzinfo=UTC),
        )

    def history(self, symbol: str, period: str) -> list[Bar]:
        self.calls.append(("history", symbol))
        self._check(symbol)
        start = date(2025, 10, 24)
        closes = [100, 110, 99, 120, 108, 130, 125]
        return [Bar(day=start + timedelta(days=i), close=Decimal(c)) for i, c in enumerate(closes)]

    def profile(self, symbol: str) -> CompanyProfile:
        self._check(symbol)
        return CompanyProfile(
            symbol=symbol,
            name=f"{symbol} Ltd",
            sector="Energy",
            industry="Oil & Gas",
            trailing_pe=Decimal("21.55"),
            dividend_yield_pct=Decimal("0.5"),
            market_cap=Decimal("16103642435650"),
            currency="INR",
            summary="Makes things.",
        )

    def search(self, query: str) -> list[SymbolMatch]:
        return [SymbolMatch(symbol="TMCV.NS", name="Tata Motors", exchange="NSE", kind="EQUITY")]

    def fx_rate(self, base: str, quote: str) -> Decimal:
        return (
            Decimal("94.93") if (base, quote) == ("USD", "INR") else Decimal(1) / Decimal("94.93")
        )
