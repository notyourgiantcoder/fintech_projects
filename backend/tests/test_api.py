from io import BytesIO

import pytest
from fakes import FakeMarketData, ScriptedChatClient, call, tool_results
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from finbo import graph, research
from finbo.api import app
from finbo.api import me as me_routes
from finbo.api.deps import get_market_data, set_store
from finbo.llm import ConfiguredProvider, Provider
from finbo.store import Store


@pytest.fixture
def store():
    s = Store("sqlite://")
    set_store(s)
    yield s
    set_store(None)


@pytest.fixture
def client(monkeypatch, store):
    for var in ("GITHUB_TOKEN", "GOOGLE_API_KEY", "CLERK_PUBLISHABLE_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FINBO_DEV_AUTH", "1")
    app.dependency_overrides[get_market_data] = FakeMarketData
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def ready(client):
    client.post("/api/me/setup", json={"market": "in"})
    return client


# ---------- public ----------


def test_health(client):
    body = client.get("/api/health").json()
    assert body["auth"] == "dev" and body["microsoft"] is False
    assert [p["configured"] for p in body["providers"]] == [False, False]


def test_demo_is_public_and_stores_nothing(client, monkeypatch, store):
    monkeypatch.delenv("FINBO_DEV_AUTH")
    res = client.get("/api/demo", params={"market": "in", "extra_debt_payment": 5000})
    assert res.json()["debt"]["comparison"]["interest_saved_with_avalanche"] == "2889.06"
    assert store.load_workspace("dev-user") is None


# ---------- workspace ----------


def test_me_requires_setup_first(client):
    assert client.get("/api/me").json()["detail"] == "not_set_up"


def test_setup_and_overview(ready):
    body = ready.get("/api/me", params={"extra_debt_payment": 5000}).json()
    assert body["currency"] == "INR" and body["watchlist"] == []
    assert body["sources"] == {"transactions": "sample", "profile": "sample"}
    assert body["debt"]["monthly_budget"] == "22950.00"


def test_data_survives_a_restart(ready, store):
    ready.post("/api/me/classify", json={"category": "Gym", "bucket": "wants"})
    fresh = TestClient(app)  # new client, same database
    assert fresh.get("/api/me").json()["overrides"] == {"Gym": "wants"}


def test_emergency_fund_contribution_param(ready):
    body = ready.get("/api/me", params={"ef_contribution": 10000}).json()
    assert body["emergency_fund"]["plan"]["monthly_contribution"] == "10000.00"


def test_profile_and_debts(ready):
    body = ready.put(
        "/api/me/profile",
        json={
            "monthly_income": "120000",
            "income_stability": "variable",
            "dependents": 0,
            "emergency_fund_balance": "0",
        },
    ).json()
    assert body["emergency_fund"]["plan"]["target_months"] == 6
    body = ready.put(
        "/api/me/debts",
        json=[
            {"name": "Card", "balance": "1000", "annual_rate_pct": "36", "minimum_payment": "100"}
        ],
    ).json()
    assert body["profile"]["debts"][0]["currency"] == "INR"
    assert (
        ready.put(
            "/api/me/debts",
            json=[{"name": "", "balance": "-1", "annual_rate_pct": "500", "minimum_payment": "0"}],
        ).status_code
        == 422
    )


def test_upload(ready):
    good = b'Date,Category,Amount\n01/09/2026,Rent,"Rs. 20,000"\n05/09/2026,Groceries,4500\n'
    res = ready.post("/api/me/transactions", files={"file": ("s.csv", good, "text/csv")})
    assert res.json()["spending"]["total_outflow"] == "24500.00"
    bad = b"Date,Category,Amount\n2026-09-01,Rent,abc\n"
    res = ready.post("/api/me/transactions", files={"file": ("s.csv", bad, "text/csv")})
    assert res.status_code == 422 and res.json()["errors"][0]["column"] == "amount"


def test_approvals_activity_and_delete(ready):
    ready.post("/api/me/approvals", json={"subject": "Debt plan", "decision": "approved"})
    assert [a["decision"] for a in ready.get("/api/me").json()["approvals"]] == ["approved"]
    assert ready.get("/api/me/activity").json()[0]["kind"] == "setup"
    assert ready.delete("/api/me").status_code == 204
    assert ready.get("/api/me").status_code == 404
    assert ready.get("/api/me/activity").json() == []


# ---------- ask (guarded, audited) ----------


def scripted(policy):
    p = Provider("scripted", "https://example.test", "X", "X", "scripted")
    return [ConfiguredProvider(provider=p, model="scripted", client=ScriptedChatClient(policy))]


def test_ask_without_llm_keys(ready):
    res = ready.post("/api/me/ask", json={"question": "Am I okay?"})
    assert res.status_code == 503 and "GITHUB_TOKEN" in res.json()["detail"]


def test_ask_is_guarded_and_audited(ready, monkeypatch):
    def policy(instructions, messages):
        results = tool_results(messages)
        if "You are Finbo" in instructions:
            return (
                ["Avalanche saves ₹2,889.06 but ₹1,234 is made up."]
                if results
                else [call("snowy", task="compare")]
            )
        return (
            [f"S: {results[0]}"]
            if results
            else [call("compare_debt_strategies", extra_monthly_payment=5000)]
        )

    monkeypatch.setattr(me_routes, "configured_providers", lambda: scripted(policy))
    body = ready.post(
        "/api/me/ask", json={"question": "My PAN is ABCPE1234F. Which debt first?"}
    ).json()
    assert body["checks"]["pii_redacted"] == {"PAN": 1}
    assert body["checks"]["unverified_figures"] == ["₹1,234"]
    assert [t["name"] for t in body["trace"]] == ["snowy", "compare_debt_strategies"]

    event = ready.get("/api/me/activity").json()[0]
    assert event["kind"] == "ask"
    assert event["summary"] == "My PAN is [PAN]. Which debt first?"  # never the raw PAN
    assert event["payload"]["checks"]["unverified_figures"] == ["₹1,234"]


def test_refusals_are_audited(ready, monkeypatch):
    monkeypatch.setattr(me_routes, "configured_providers", lambda: scripted(lambda i, m: ["x"]))
    body = ready.post("/api/me/ask", json={"question": "How do I launder black money?"}).json()
    assert body["checks"]["refused"] == "money laundering" and body["provider"] is None
    assert ready.get("/api/me/activity").json()[0]["kind"] == "refused"


# ---------- markets ----------


def test_watchlist(ready):
    assert ready.put(
        "/api/me/watchlist", json={"symbols": ["reliance", "TCS", "reliance"]}
    ).json() == [
        "RELIANCE.NS",
        "TCS.NS",
    ]
    rows = ready.get("/api/me/watchlist").json()
    assert rows[0]["quote"]["price"] == "1190.00"
    assert ready.put("/api/me/watchlist", json={"symbols": ["not valid!"]}).status_code == 422
    assert ready.put("/api/me/watchlist", json={"symbols": ["A"] * 21}).status_code == 422


def test_symbol_detail(ready, monkeypatch):
    monkeypatch.setattr(research, "search_news", lambda q, m, n: [])
    body = ready.get("/api/market/symbol/reliance").json()
    assert body["symbol"] == "RELIANCE.NS" and body["stats"]["return_pct"] == "25.00"
    assert body["profile"]["sector"] == "Energy" and "filings" not in body
    assert ready.get("/api/market/symbol/UNKNOWN").status_code == 404


def test_market_endpoints_need_sign_in(client, monkeypatch):
    monkeypatch.delenv("FINBO_DEV_AUTH")
    assert client.get("/api/market/search", params={"q": "tata"}).status_code == 503


# ---------- Excel and OneDrive ----------


def mark_first_proposal(data: bytes, status: str) -> bytes:
    wb = load_workbook(BytesIO(data))
    wb["Approvals"]["C3"] = status
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def test_excel_round_trip(ready):
    res = ready.get("/api/me/export.xlsx")
    assert res.headers["content-type"].startswith("application/vnd.openxmlformats")
    edited = mark_first_proposal(res.content, "Approved")
    body = ready.post("/api/me/import.xlsx", files={"file": ("plan.xlsx", edited)}).json()
    (approval,) = body["recorded"]
    assert approval["subject"].startswith("Debt plan") and approval["source"] == "excel"
    # Importing the same file again records nothing new.
    assert (
        ready.post("/api/me/import.xlsx", files={"file": ("plan.xlsx", edited)}).json()["recorded"]
        == []
    )


def test_import_rejects_non_workbooks(ready):
    res = ready.post("/api/me/import.xlsx", files={"file": ("x.xlsx", b"not excel")})
    assert res.status_code == 422


def test_onedrive_push_and_pull(ready, monkeypatch):
    saved = {}

    def upload(token, content, path=graph.DEFAULT_PATH, http=None):
        saved.update(token=token, content=content)
        return "https://onedrive.example/plan.xlsx"

    monkeypatch.setattr(graph, "upload", upload)
    monkeypatch.setattr(
        graph,
        "download",
        lambda token, path=graph.DEFAULT_PATH, http=None: mark_first_proposal(
            saved["content"], "Sent back"
        ),
    )
    headers = {"X-Graph-Token": "t" * 30}
    assert (
        ready.post("/api/me/onedrive/push", headers=headers)
        .json()["web_url"]
        .startswith("https://")
    )
    (approval,) = ready.post("/api/me/onedrive/pull", headers=headers).json()["recorded"]
    assert approval["decision"] == "sent_back"
    assert ready.post("/api/me/onedrive/push").status_code == 422  # token header required
