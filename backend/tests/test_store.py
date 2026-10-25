from datetime import UTC, datetime

import pytest

from finbo.session import FinanceSession
from finbo.store import Approval, Store, Workspace, database_url


@pytest.fixture
def store():
    return Store("sqlite://")


def test_workspace_round_trip(store):
    ws = Workspace(market="in", finance=FinanceSession.sample("in"), watchlist=["RELIANCE.NS"])
    ws.finance.bucket_overrides["Gym"] = "wants"
    store.save_workspace("u1", ws)

    loaded = store.load_workspace("u1")
    assert loaded.market == "in" and loaded.watchlist == ["RELIANCE.NS"]
    assert loaded.finance.profile == ws.finance.profile
    assert loaded.finance.transactions == ws.finance.transactions
    assert loaded.finance.bucket_overrides == {"Gym": "wants"}
    assert loaded.finance.budget_report() == ws.finance.budget_report()


def test_save_updates_in_place(store):
    ws = Workspace(market="us", finance=FinanceSession.sample("us"))
    store.save_workspace("u1", ws)
    ws.transactions_source = "uploaded"
    store.save_workspace("u1", ws)
    assert store.load_workspace("u1").transactions_source == "uploaded"


def test_approvals_and_events_are_per_user(store):
    a = Approval(id="a1", subject="Debt plan", decision="approved", decided_at=datetime.now(UTC))
    store.add_approval("u1", a)
    store.add_event("u1", "ask", "q", {"answer": "x"})
    store.add_event("u2", "ask", "other", {})
    assert [x.id for x in store.list_approvals("u1")] == ["a1"]
    assert store.list_approvals("u1")[0].decided_at.tzinfo is not None
    assert [e.summary for e in store.list_events("u1")] == ["q"]


def test_delete_user_removes_everything(store):
    store.save_workspace("u1", Workspace(market="in", finance=FinanceSession.sample("in")))
    store.add_event("u1", "ask", "q", {})
    store.add_approval(
        "u1", Approval(id="a", subject="s", decision="approved", decided_at=datetime.now(UTC))
    )
    store.delete_user("u1")
    assert store.load_workspace("u1") is None
    assert store.list_events("u1") == [] and store.list_approvals("u1") == []


def test_file_database_survives_reopen(tmp_path):
    url = f"sqlite:///{tmp_path / 'f.db'}"
    Store(url).save_workspace("u1", Workspace(market="in", finance=FinanceSession.sample("in")))
    assert Store(url).load_workspace("u1") is not None


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        (
            "postgresql://u:p@host/db?sslmode=require",
            "postgresql+psycopg://u:p@host/db?sslmode=require",
        ),
    ],
)
def test_neon_urls_get_a_driver(monkeypatch, given, expected):
    monkeypatch.setenv("DATABASE_URL", given)
    assert database_url() == expected


def test_default_is_sqlite_file(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FINBO_DB_PATH", str(tmp_path / "x.db"))
    assert database_url() == f"sqlite:///{tmp_path / 'x.db'}"
