"""CSV transaction ingestion.

Bad rows are collected as `RowError`s instead of aborting the whole import, so the
UI can show them to the user for correction (human-in-the-loop step #1).
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import BaseModel

from .models import Transaction
from .money import Currency

REQUIRED_COLUMNS = ("date", "category", "amount")

_CURRENCY_TOKENS = re.compile(r"(?i)(rs\.?|inr|usd|₹|\$)")
_ISO_FORMAT = "%Y-%m-%d"
_DAYFIRST_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")
_MONTHFIRST_FORMATS = ("%m/%d/%Y", "%m-%d-%Y")


class CsvSchemaError(ValueError):
    """The file as a whole is unusable (e.g. required columns missing)."""


class RowError(BaseModel):
    line: int
    column: str
    value: str
    message: str


class IngestResult(BaseModel):
    transactions: list[Transaction]
    errors: list[RowError]

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_amount(raw: str) -> Decimal:
    """Parse '₹1,23,456.50', '$1,200', 'Rs. 500', '(45.00)', '-45' into a Decimal."""
    text = raw.strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    text = _CURRENCY_TOKENS.sub("", text).replace(",", "").replace(" ", "")
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    if not text:
        raise ValueError("empty amount")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"not a number: {raw!r}") from None
    if not value.is_finite():
        raise ValueError(f"not a finite number: {raw!r}")
    return -value if negative else value


def parse_date(raw: str, *, dayfirst: bool) -> date:
    """ISO dates always work; slash/dash dates follow the locale (India: DD/MM, US: MM/DD)."""
    text = raw.strip()
    formats = (_ISO_FORMAT, *(_DAYFIRST_FORMATS if dayfirst else _MONTHFIRST_FORMATS))
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    order = "DD/MM/YYYY" if dayfirst else "MM/DD/YYYY"
    raise ValueError(f"unrecognised date {raw!r}; use YYYY-MM-DD or {order}")


def normalize_category(raw: str) -> str:
    """'  food   & dining ' -> 'Food & Dining'; acronyms like 'EMI' are preserved."""
    return " ".join(word[:1].upper() + word[1:] for word in raw.split())


def parse_transactions_csv(
    source: str | Path,
    currency: Currency,
    *,
    dayfirst: bool | None = None,
) -> IngestResult:
    """Parse a Date,Category,Amount[,Description] CSV.

    `source` is a path or the CSV text itself. `dayfirst` defaults to the currency's
    locale convention (INR -> True, USD -> False).
    """
    if dayfirst is None:
        dayfirst = currency is Currency.INR
    text = Path(source).read_text(encoding="utf-8-sig") if isinstance(source, Path) else source

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CsvSchemaError("CSV is empty")
    header_map = {name.strip().lower(): name for name in reader.fieldnames if name}
    missing = [c for c in REQUIRED_COLUMNS if c not in header_map]
    if missing:
        raise CsvSchemaError(f"Missing required column(s): {', '.join(missing)}")

    transactions: list[Transaction] = []
    errors: list[RowError] = []
    for row in reader:
        line = reader.line_num
        values = {key: (row.get(original) or "").strip() for key, original in header_map.items()}
        if not any(values.values()):
            continue

        row_errors: list[RowError] = []
        parsed_date = parsed_amount = None
        try:
            parsed_date = parse_date(values["date"], dayfirst=dayfirst)
        except ValueError as e:
            row_errors.append(
                RowError(line=line, column="date", value=values["date"], message=str(e))
            )
        try:
            parsed_amount = parse_amount(values["amount"])
        except ValueError as e:
            row_errors.append(
                RowError(line=line, column="amount", value=values["amount"], message=str(e))
            )
        category = normalize_category(values["category"])
        if not category:
            row_errors.append(
                RowError(line=line, column="category", value="", message="category is empty")
            )

        if row_errors:
            errors.extend(row_errors)
            continue
        transactions.append(
            Transaction(
                date=parsed_date,
                category=category,
                amount=parsed_amount,
                currency=currency,
                description=values.get("description", ""),
            )
        )
    return IngestResult(transactions=transactions, errors=errors)
