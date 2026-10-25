import pytest
from fakes import FakeMarketData
from fastapi.testclient import TestClient

from finbo import research
from finbo.api import app
from finbo.api.deps import get_market_data, set_store
from finbo.store import Store


@pytest.fixture
def client(monkeypatch):
    for var in ("GITHUB_TOKEN", "GOOGLE_API_KEY", "CLERK_PUBLISHABLE_KEY", "TELEGRAM_BOT_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FINBO_DEV_AUTH", "1")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "FinboCrewBot")
    monkeypatch.setattr(research, "market_headlines", lambda m: [])
    store = Store("sqlite://")
    set_store(store)
    app.dependency_overrides[get_market_data] = FakeMarketData
    c = TestClient(app)
    c.post("/api/me/setup", json={"market": "in"})
    yield c
    app.dependency_overrides.clear()
    set_store(None)


def test_crew_is_public(client, monkeypatch):
    monkeypatch.delenv("FINBO_DEV_AUTH")
    crew = client.get("/api/crew").json()
    assert [m["name"] for m in crew] == ["Finbo", "Penny", "Hazel", "Snowy", "Bruno", "Scout"]
    assert crew[3]["quick_actions"][0] == {
        "id": "debt_free",
        "label": "When will I be debt-free?",
        "needs": None,
    }


def test_quick_send_history_and_act(client):
    asked, reply = client.post("/api/me/chat/snowy/quick", json={"action": "debt_free"}).json()
    assert asked["text"] == "When will I be debt-free?" and reply["author"] == "snowy"
    done = client.post(
        "/api/me/chat-action", json={"message_id": reply["id"], "card": 0, "action": 0}
    ).json()
    assert "Approved" in done[0]["text"]
    assert client.get("/api/me").json()["approvals"][0]["subject"].startswith("Debt plan")

    _, offline = client.post("/api/me/chat/finbo", json={"text": "how do I cut spending?"}).json()
    assert offline["author"] == "penny" and offline["meta"]["mode"] == "offline"

    history = client.get("/api/me/chat/snowy").json()
    assert [m["role"] for m in history] == ["user", "agent", "agent"]
    assert history[0]["created_at"] <= history[-1]["created_at"]


def test_bad_inputs(client):
    assert client.post("/api/me/chat/nobody", json={"text": "hi"}).status_code == 422
    assert client.post("/api/me/chat/snowy/quick", json={"action": "fly"}).status_code == 422
    assert (
        client.post(
            "/api/me/chat-action", json={"message_id": 999, "card": 0, "action": 0}
        ).status_code
        == 422
    )
    assert client.post("/api/me/chat/finbo", json={"text": ""}).status_code == 422


def test_clear_thread(client):
    client.post("/api/me/chat/penny/quick", json={"action": "spending"})
    assert client.delete("/api/me/chat/penny").status_code == 204
    assert client.get("/api/me/chat/penny").json() == []


def test_telegram_link_code(client):
    status = client.get("/api/me/telegram").json()
    assert status == {
        "linked": False,
        "bot": {
            "configured": False,
            "username": "FinboCrewBot",
            "url": "https://t.me/FinboCrewBot",
        },
    }
    code = client.post("/api/me/telegram/code").json()
    assert (
        len(code["code"]) == 8
        and code["deep_link"] == f"https://t.me/FinboCrewBot?start=link-{code['code']}"
    )


def test_delete_me_removes_chats_and_links(client):
    from finbo.api.deps import get_store

    client.post("/api/me/chat/penny/quick", json={"action": "spending"})
    code = client.post("/api/me/telegram/code").json()["code"]
    get_store().redeem_link_code(code, "42")
    assert client.get("/api/me/telegram").json()["linked"] is True
    client.delete("/api/me")
    assert get_store().list_messages("dev-user", "penny") == []
    assert get_store().linked_user("42") is None


def test_latest_per_thread(client):
    assert client.get("/api/me/chats").json() == {}
    client.post("/api/me/chat/hazel/quick", json={"action": "safety_net"})
    latest = client.get("/api/me/chats").json()
    assert list(latest) == ["hazel"] and latest["hazel"]["role"] == "agent"


def test_public_demo_reply(client, monkeypatch):
    monkeypatch.delenv("FINBO_DEV_AUTH")
    body = client.get(
        "/api/demo/quick/snowy/debt_free", params={"market": "in", "arg": "5000"}
    ).json()
    assert body["author"] == "snowy" and "debt-free in 15 months" in body["text"]
    assert body["cards"][0]["actions"] == []
    assert client.get("/api/demo/quick/bruno/check").status_code == 404
