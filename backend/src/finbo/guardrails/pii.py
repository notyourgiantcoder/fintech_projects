"""Pattern-based PII redaction for Indian and US identifiers.

Runs before any text reaches an LLM provider. Checksummed identifiers (Aadhaar's
Verhoeff digit, card numbers' Luhn digit) are validated, so ordinary 12- or 16-digit
numbers such as amounts are not redacted by mistake.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

# Verhoeff tables (Aadhaar check digit).
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_valid(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# Boundaries for bare digit runs: not inside a longer number or a decimal/grouped amount,
# but a trailing sentence period or comma is fine.
_NUM_START = r"(?<!\d)(?<!\d[.,])"
_NUM_END = r"(?!\d)(?![.,]\d)"


@dataclass(frozen=True)
class _Rule:
    label: str
    pattern: re.Pattern[str]
    validate: object = None  # callable(digits) -> bool, applied to the digits only


_RULES: list[_Rule] = [
    _Rule("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    # UPI IDs look like name@bank with no dot in the handle part.
    _Rule("UPI_ID", re.compile(r"\b[\w.-]{2,}@(?!\S*\.)[a-zA-Z]{2,}\b")),
    _Rule("PAN", re.compile(r"\b[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]\b")),
    _Rule("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    _Rule(
        "AADHAAR",
        re.compile(rf"{_NUM_START}[2-9]\d{{3}}[ -]?\d{{4}}[ -]?\d{{4}}{_NUM_END}"),
        verhoeff_valid,
    ),
    _Rule(
        "CARD",
        re.compile(rf"{_NUM_START}(?:\d[ -]?){{12,18}}\d{_NUM_END}"),
        luhn_valid,
    ),
    _Rule("SSN", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    _Rule(
        "ACCOUNT_NUMBER",
        re.compile(r"(?i)(?:a/c|acct|account)(?:\s*(?:no\.?|number|#))?\s*[:#]?\s*\d{9,18}\b"),
    ),
    _Rule("PHONE", re.compile(rf"{_NUM_START}(?:\+91[ -]?)?[6-9]\d{{4}}[ -]?\d{{5}}{_NUM_END}")),
    _Rule(
        "PHONE",
        re.compile(
            rf"{_NUM_START}(?:\+1[ -]?)?\(?[2-9]\d{{2}}\)?[ -.]\d{{3}}[ -.]\d{{4}}{_NUM_END}"
        ),
    ),
]


@dataclass(frozen=True)
class Redaction:
    text: str
    found: dict[str, int]

    @property
    def changed(self) -> bool:
        return bool(self.found)


def redact(text: str) -> Redaction:
    found: Counter[str] = Counter()
    for rule in _RULES:

        def replace(m: re.Match[str], rule: _Rule = rule) -> str:
            if rule.validate is not None:
                digits = re.sub(r"\D", "", m.group(0))
                if not rule.validate(digits):  # type: ignore[operator]
                    return m.group(0)
            found[rule.label] += 1
            return f"[{rule.label}]"

        text = rule.pattern.sub(replace, text)
    return Redaction(text=text, found=dict(found))
