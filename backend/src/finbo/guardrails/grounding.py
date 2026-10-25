"""Output checks: every figure in an answer must come from a tool result, and the wording
must not promise returns.

The agents are instructed never to calculate. This module verifies that instruction was
followed: it extracts each money amount and percentage from the answer and looks for it
among the numbers that tools actually returned (allowing for the rounding a writer
naturally does, such as ₹42,415.50 written as ₹42,416 or 44.65% as 44.6%).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

DISCLAIMER = "This is educational guidance, not regulated financial advice."

# Figures an answer may state without a tool: the 50/30/20 guide and common round numbers
# from the user's own question are added separately.
_GUIDE_CONSTANTS = {Decimal(n) for n in (20, 30, 50, 80, 100)}

_MONEY = re.compile(
    r"(?:₹|Rs\.?\s?|INR\s?|\$|USD\s?)\s?(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(lakh|crore|k|m|bn|million|billion)?\b",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_RISKY = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"guaranteed\s+(returns?|profits?|gains?)",
        r"risk[- ]free\s+(returns?|investment)",
        r"can(?:no|')t\s+lose",
        r"(will|is\s+sure\s+to)\s+(definitely\s+)?(double|go\s+up|rise|rally)",
        r"100%\s+safe",
    )
]
_SCALE = {
    "lakh": Decimal(100_000),
    "crore": Decimal(10_000_000),
    "k": Decimal(1_000),
    "m": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "bn": Decimal(1_000_000_000),
    "billion": Decimal(1_000_000_000),
}


@dataclass
class GroundingReport:
    checked: int = 0
    unverified: list[str] = field(default_factory=list)
    risky_phrases: list[str] = field(default_factory=list)
    disclaimer_added: bool = False

    @property
    def passed(self) -> bool:
        return not self.unverified and not self.risky_phrases


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None


def _numbers_in(value: object) -> Iterable[Decimal]:
    """Every number inside a tool result: JSON numbers, numeric strings, numbers in text."""
    if isinstance(value, bool):
        return
    if isinstance(value, int | float | Decimal):
        yield Decimal(str(value))
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in "{[":
            try:
                yield from _numbers_in(json.loads(stripped))
                return
            except ValueError:
                pass
        for m in re.finditer(r"-?\d[\d,]*(?:\.\d+)?", value):
            d = _to_decimal(m.group(0))
            if d is not None:
                yield d
    elif isinstance(value, dict):
        for v in value.values():
            yield from _numbers_in(v)
    elif isinstance(value, list | tuple):
        for v in value:
            yield from _numbers_in(v)


def _variants(n: Decimal) -> set[Decimal]:
    """Ways a writer may legitimately round a source number."""
    n = abs(n)
    out = {n}
    for places in ("1", "0.1", "0.01"):
        out.add(n.quantize(Decimal(places), rounding=ROUND_HALF_UP))
        out.add(n.quantize(Decimal(places), rounding=ROUND_DOWN))
    # 16103642435650 market cap -> "₹16.1 lakh crore" style statements are checked
    # after scaling, so also keep coarse versions of large numbers.
    if n >= 1000:
        for unit in _SCALE.values():
            if n >= unit:
                scaled = n / unit
                for places in ("1", "0.1", "0.01"):
                    out.add((scaled.quantize(Decimal(places), rounding=ROUND_HALF_UP)) * unit)
    return out


def check_answer(
    answer: str, tool_results: Iterable[object], question: str = ""
) -> tuple[str, GroundingReport]:
    known: set[Decimal] = set(_GUIDE_CONSTANTS)
    for result in tool_results:
        for n in _numbers_in(result):
            known |= _variants(n)
    for n in _numbers_in(question):
        known |= _variants(n)

    report = GroundingReport()
    for m in _MONEY.finditer(answer):
        value = _to_decimal(m.group(1))
        if value is None:
            continue
        if m.group(2):
            value *= _SCALE[m.group(2).lower()]
        report.checked += 1
        if value not in known:
            report.unverified.append(m.group(0).strip())
    for m in _PERCENT.finditer(answer):
        value = _to_decimal(m.group(1))
        if value is None:
            continue
        report.checked += 1
        if value not in known:
            report.unverified.append(m.group(0))

    for pattern in _RISKY:
        hit = pattern.search(answer)
        if hit:
            report.risky_phrases.append(hit.group(0))

    if "not regulated financial advice" not in answer.lower():
        answer = f"{answer.rstrip()}\n\n{DISCLAIMER}"
        report.disclaimer_added = True
    return answer, report
