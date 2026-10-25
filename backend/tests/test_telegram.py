"""Telegram bot handlers with fake update objects (no network)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fakes import FakeMarketData

from finbo.chat import ChatService
from finbo.session import FinanceSession
from finbo.store import ChatMessage, Store, Workspace
from finbo.telegram_bot import FinboBot, render_card, render_message, user_id_for


class Target:
    """Stands in for a Telegram message: records what the bot replied."""

    def __init__(self):
        self.sent = []

    async def reply_text(self, text, **kwargs):
        self.sent.append((text, kwargs.get("reply_markup")))


class Doc:
    def __init__(self, name, data):
        self.file_name, self.file_size, self._data = name, len(data), data

    async def get_file(self):
        data = self._data

        class F:
            async def download_as_bytearray(self):
                return bytearray(data)

        return F()


def update(text="", telegram_id=42, document=None, data=None):
    message = Target()
    message.text, message.document = text, document
    chat = SimpleNamespace(send_action=lambda *_: _noop())
    query = None
    if data is not None:
        query = SimpleNamespace(data=data, message=message, answer=lambda: _noop())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=telegram_id),
        effective_chat=chat,
        message=message,
        callback_query=query,
    )


async def _noop():
    return None


def context(args=None):
    return SimpleNamespace(args=args or [], user_data={})


@pytest.fixture
def store():
    return Store("sqlite://")


@pytest.fixture
def bot(store):
    return FinboBot(store, ChatService(store, market_data=FakeMarketData, providers=lambda: []))


def labels(markup):
    return [b.text for row in markup.inline_keyboard for b in row] if markup else []


async def test_start_offers_setup_then_sets_up(bot, store):
    u = update()
    await bot.start(u, context())
    text, markup = u.message.sent[0]
    assert "Let’s set you up" in text and labels(markup) == ["India (₹)", "United States ($)"]

    u = update(data="setup:in")
    await bot.button(u, context())
    assert store.load_workspace("tg:42").market == "in"
    assert "Meet the crew" in u.message.sent[0][0]


async def test_setup_never_overwrites_existing_data(bot, store):
    ws = Workspace(market="us", finance=FinanceSession.sample("us"))
    store.save_workspace("tg:42", ws)
    await bot.button(update(data="setup:in"), context())
    assert store.load_workspace("tg:42").market == "us"


async def test_agent_command_switches_agent_and_answers(bot, store):
    store.save_workspace("tg:42", Workspace(market="in", finance=FinanceSession.sample("in")))
    ctx = context(["when", "am", "I", "debt", "free?"])
    u = update()
    await bot.talk(u, ctx, "snowy")
    assert ctx.user_data["agent"] == "snowy"
    text, markup = u.message.sent[-1]
    assert text.startswith("🦉 <b>Snowy</b>") and "debt-free in 20 months" in text
    assert "Approve this plan" in labels(markup)

    # A plain follow-up goes to the same agent.
    u = update("avalanche or snowball?")
    await bot.text(u, ctx)
    assert u.message.sent[-1][0].startswith("🦉 <b>Snowy</b>")


async def test_agent_command_without_text_greets_with_quick_buttons(bot):
    u = update()
    await bot.talk(u, context(), "hazel")
    text, markup = u.message.sent[0]
    assert "Hazel" in text and labels(markup) == [
        "How big should my safety net be?",
        "How fast can I fill it?",
    ]


async def test_approve_button_from_telegram(bot, store):
    store.save_workspace("tg:42", Workspace(market="in", finance=FinanceSession.sample("in")))
    ctx = context(["debt", "free?"])
    await bot.talk(update(), ctx, "snowy")
    reply = store.list_messages("tg:42", "snowy")[-1]
    u = update(data=f"a:{reply.id}:0:0")
    await bot.button(u, ctx)
    assert store.list_approvals("tg:42")[0].source == "telegram"
    assert "Approved" in u.message.sent[-1][0]


async def test_stale_button(bot, store):
    store.save_workspace("tg:42", Workspace(market="in", finance=FinanceSession.sample("in")))
    u = update(data="a:999:0:0")
    await bot.button(u, context())
    assert "expired" in u.message.sent[0][0]


async def test_link_shares_web_data(bot, store):
    store.save_workspace("web-user", Workspace(market="us", finance=FinanceSession.sample("us")))
    store.create_link_code("web-user", "ABCD2345", datetime.now(UTC) + timedelta(minutes=10))
    u = update()
    await bot.link(u, context(["abcd2345"]))
    assert "Linked" in u.message.sent[0][0]
    assert user_id_for(store, 42) == "web-user"
    # Code is single use.
    u = update(telegram_id=7)
    await bot.link(u, context(["ABCD2345"]))
    assert "didn’t work" in u.message.sent[0][0]


async def test_deep_link_start_links(bot, store):
    store.create_link_code("web-user", "ZZZZ9999", datetime.now(UTC) + timedelta(minutes=10))
    await bot.start(update(), context(["link-ZZZZ9999"]))
    assert user_id_for(store, 42) == "web-user"


async def test_expired_code(bot, store):
    store.create_link_code("web-user", "OLDC0DE2", datetime.now(UTC) - timedelta(minutes=1))
    u = update()
    await bot.link(u, context(["OLDC0DE2"]))
    assert user_id_for(store, 42) == "tg:42"


async def test_reset_on_linked_chat_only_unlinks(bot, store):
    store.save_workspace("web-user", Workspace(market="us", finance=FinanceSession.sample("us")))
    store.create_link_code("web-user", "ABCD2345", datetime.now(UTC) + timedelta(minutes=10))
    await bot.link(update(), context(["ABCD2345"]))
    await bot.button(update(data="reset:yes"), context())
    assert store.load_workspace("web-user") is not None
    assert user_id_for(store, 42) == "tg:42"


async def test_reset_deletes_telegram_only_data(bot, store):
    store.save_workspace("tg:42", Workspace(market="in", finance=FinanceSession.sample("in")))
    await bot.button(update(data="reset:yes"), context())
    assert store.load_workspace("tg:42") is None


async def test_csv_statement_upload(bot, store):
    store.save_workspace("tg:42", Workspace(market="in", finance=FinanceSession.sample("in")))
    csv = b'Date,Category,Amount\n01/09/2026,Rent,"Rs. 20,000"\n05/09/2026,Groceries,4500\n'
    u = update(document=Doc("sept.csv", csv))
    await bot.document(u, context())
    assert "Got 2 transactions" in u.message.sent[0][0]
    assert store.load_workspace("tg:42").transactions_source == "uploaded"

    u = update(document=Doc("bad.csv", b"Date,Category,Amount\n2026-09-01,Rent,abc\n"))
    await bot.document(u, context())
    assert "Line 2, amount" in u.message.sent[0][0]


def test_rendering_escapes_html_and_numbers_buttons():
    msg = ChatMessage(
        id=5,
        thread="scout",
        role="agent",
        author="scout",
        text="<script>alert(1)</script> & more",
        cards=[
            {
                "kind": "news",
                "title": "News",
                "data": {
                    "items": [
                        {"title": "A <b>", "source": "Mint", "link": "https://a", "date": "1 Oct"}
                    ]
                },
                "actions": [{"kind": "quick", "label": "More", "payload": {}}],
            }
        ],
        meta={"contributors": [], "note": None},
        channel="telegram",
        created_at=datetime.now(UTC),
    )
    text, rows = render_message(msg)
    assert "&lt;script&gt;" in text and "<script>" not in text
    assert '<a href="https://a">A &lt;b&gt;</a> (Mint, 1 Oct)' in text
    assert rows == [[("More", "a:5:0:0")]]


def test_safety_card_progress_bar():
    card = {
        "kind": "safety",
        "title": "Your safety net",
        "data": {
            "progress": 0.38,
            "have": "₹60,000",
            "target": "₹1,59,183",
            "funded": False,
            "gap": "₹99,183",
            "months_to_target": 5,
            "monthly": "₹21,208",
        },
        "actions": [],
    }
    assert "▓▓▓▓░░░░░░ ₹60,000 of ₹1,59,183" in render_card(card)
