"""Requests Finbo refuses before any LLM call: clear help with financial crime."""

from __future__ import annotations

import re
from dataclasses import dataclass

_BLOCKED: list[tuple[str, re.Pattern[str]]] = [
    (
        "tax evasion",
        re.compile(
            r"(?i)\b(evade|evading|dodge|hide\s+(income|money)\s+from)\b[^.?\n]{0,30}\b(tax|taxes|income\s+tax|irs|it\s+department)\b|\bnot\s+(declare|report)\b[^.?\n]{0,30}\b(income|cash)\b"
        ),
    ),
    (
        "money laundering",
        re.compile(
            r"(?i)\b(launder|laundering|clean)\b[^.?\n]{0,20}\b(money|cash|black\s+money)\b"
        ),
    ),
    (
        "fraud",
        re.compile(
            r"(?i)\b(fake|forged?|forging|doctor(ed)?)\b[^.?\n]{0,20}\b(invoice|bill|salary\s+slip|payslip|bank\s+statement|documents?)\b"
        ),
    ),
    (
        "insider trading",
        re.compile(
            r"(?i)\b(trade|buy|sell)\b[^.?\n]{0,40}\b(insider|non-?public|unpublished\s+price)\b"
        ),
    ),
]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    category: str | None = None

    @property
    def message(self) -> str:
        return (
            f"Finbo can’t help with {self.category}. It can help you plan within the rules, "
            "for example by showing legal tax-saving options or how to fix your budget."
        )


def check_request(text: str) -> PolicyDecision:
    for category, pattern in _BLOCKED:
        if pattern.search(text):
            return PolicyDecision(allowed=False, category=category)
    return PolicyDecision(allowed=True)
