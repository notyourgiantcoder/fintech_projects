from datetime import date
from decimal import Decimal

import pytest

from finbo.core import CsvSchemaError, Currency, parse_transactions_csv
from finbo.core.ingest import normalize_category, parse_amount, parse_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1200.00", "1200.00"),
        ("$1,200.00", "1200.00"),
        ("₹1,23,456.50", "123456.50"),
        ("Rs. 500", "500"),
        ("INR 750", "750"),
        ("(45.00)", "-45.00"),
        ("-45", "-45"),
        (" 12 ", "12"),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["", "abc", "$", "1.2.3", "NaN", "Infinity"])
def test_parse_amount_rejects_garbage(raw):
    with pytest.raises(ValueError):
        parse_amount(raw)


def test_parse_date_follows_locale():
    assert parse_date("03/04/2026", dayfirst=True) == date(2026, 4, 3)
    assert parse_date("03/04/2026", dayfirst=False) == date(2026, 3, 4)
    assert parse_date("2026-04-03", dayfirst=False) == date(2026, 4, 3)
    with pytest.raises(ValueError, match="DD/MM/YYYY"):
        parse_date("31/31/2026", dayfirst=True)


def test_normalize_category():
    assert normalize_category("  food   delivery ") == "Food Delivery"
    assert normalize_category("EMI") == "EMI"


def test_sample_india_file(samples_dir):
    result = parse_transactions_csv(samples_dir / "transactions_in.csv", Currency.INR)
    assert result.ok, result.errors
    assert len(result.transactions) == 31
    first = result.transactions[0]
    assert first.date == date(2026, 8, 1)
    assert first.amount == Decimal("22000.00")


def test_sample_us_file_with_refund(samples_dir):
    result = parse_transactions_csv(samples_dir / "transactions_us.csv", Currency.USD)
    assert result.ok, result.errors
    assert len(result.transactions) == 28
    assert any(t.amount == Decimal("-35.00") for t in result.transactions)


def test_bad_rows_are_reported_not_fatal():
    csv_text = (
        "Date,Category,Amount\n"
        "2026-01-01,Housing,1200\n"
        "not-a-date,Food,abc\n"
        "2026-01-03,,45\n"
        ",,\n"
        "2026-01-04,Transport,45.50\n"
    )
    result = parse_transactions_csv(csv_text, Currency.USD)
    assert [t.category for t in result.transactions] == ["Housing", "Transport"]
    assert {(e.line, e.column) for e in result.errors} == {
        (3, "date"),
        (3, "amount"),
        (4, "category"),
    }


def test_headers_are_case_insensitive():
    result = parse_transactions_csv(" DATE , category ,AMOUNT\n2026-01-01,Rent,10\n", Currency.USD)
    assert result.ok and len(result.transactions) == 1


def test_missing_column_is_fatal():
    with pytest.raises(CsvSchemaError, match="amount"):
        parse_transactions_csv("Date,Category\n2026-01-01,Food\n", Currency.USD)
