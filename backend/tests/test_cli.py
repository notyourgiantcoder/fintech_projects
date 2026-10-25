import pytest

from finbo import cli


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    # Never pick up the developer's real .env keys in tests.
    monkeypatch.setattr(cli, "load_env", lambda: None)


def test_report_india(capsys):
    assert cli.main(["report", "--market", "in", "--extra-debt-payment", "5000"]) == 0
    out = capsys.readouterr().out
    assert "₹95,000.00" in out
    assert "Needs your review: Gym" in out
    assert "avalanche   15 months, interest ₹40,072.19, targets HDFC Credit Card first" in out
    assert "snowball    15 months, interest ₹42,961.25, targets Two-wheeler Loan first" in out
    assert "Avalanche saves ₹2,889.06; snowball clears its first debt 3 month(s) sooner" in out


def test_report_minimums_only_strategies_tie(capsys):
    # With no extra money there is nothing to aim, so both strategies cost the same.
    assert cli.main(["report", "--market", "in"]) == 0
    assert "Avalanche saves ₹0.00" in capsys.readouterr().out


def test_report_us_with_extra_payment(capsys):
    assert cli.main(["report", "--market", "us", "--extra-debt-payment", "300"]) == 0
    out = capsys.readouterr().out
    assert "$5,200.00" in out and "extra $300.00" in out


def test_ask_without_keys_explains_setup(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert cli.main(["ask", "Am I saving enough?"]) == 2
    assert "GITHUB_TOKEN or GOOGLE_API_KEY" in capsys.readouterr().err
