"""Finbo on Telegram: one bot, the whole crew.

    /penny where does my money go?   talk to Penny (she stays the current agent)
    plain messages                   go to whoever you last talked to (Finbo by default)
    buttons                          quick questions, approvals, filing categories
    a .csv file                      becomes your statement

Works on its own (each Telegram user gets their own data, "tg:<id>"), or linked to a web
account with /link CODE, after which both share the same data and chat history.
Uses long polling, so it needs no public URL: `finbo telegram`.
"""

from __future__ import annotations

import contextlib
import html
import logging
from typing import Any

from .chat import ChatService, NotSetUp, UnknownAction
from .core import CsvSchemaError, parse_transactions_csv
from .crew import CREW
from .session import FinanceSession
from .store import ChatMessage, Store, Workspace

log = logging.getLogger(__name__)

MAX_TEXT = 3900  # Telegram's limit is 4096 characters
MAX_CSV_BYTES = 1_000_000


def user_id_for(store: Store, telegram_id: int | str) -> str:
    return store.linked_user(str(telegram_id)) or f"tg:{telegram_id}"


# ---------- rendering (pure functions, unit-tested) ----------


def _e(text: Any) -> str:
    return html.escape(str(text), quote=False)


def _bar(progress: float, width: int = 10) -> str:
    filled = max(0, min(width, round(progress * width)))
    return "▓" * filled + "░" * (width - filled)


def render_card(card: dict[str, Any]) -> str:
    kind, d = card["kind"], card["data"]
    lines = [f"<b>{_e(card['title'])}</b>"]
    if kind == "summary":
        lines += [
            f"Left over each month: <b>{_e(d['left_over'])}</b>",
            f"Savings rate: {_e(d['savings_rate'])}",
            f"Safety net: {_e(d['safety'])}",
            f"Debt-free: {_e(d['debt_free'])}",
        ]
    elif kind == "spending":
        lines.append(f"Income {_e(d['income'])}, spending {_e(d['spending'])} a month")
        lines += [
            f"{_e(r['label'])}: {_e(r['amount'])} ({_e(r['pct_text'])}, guide {_e(r['guide'])})"
            for r in d["rows"]
        ]
        lines.append(
            "Biggest: " + ", ".join(f"{_e(t['category'])} {_e(t['amount'])}" for t in d["top"][:3])
        )
    elif kind == "safety":
        lines.append(f"{_bar(d['progress'])} {_e(d['have'])} of {_e(d['target'])}")
        if not d["funded"]:
            lines.append(
                f"{_e(d['gap'])} to go: about {_e(d['months_to_target'])} months "
                f"at {_e(d['monthly'])} a month"
            )
    elif kind == "debt":
        lines += [
            f"Debt-free: <b>{_e(d['debt_free'])}</b> "
            f"({_e(d['months'])} months, {_e(d['method'])} method)",
            f"Paying {_e(d['monthly'])} a month, {_e(d['interest'])} interest in total",
            "Order: " + ", then ".join(f"{_e(o['name'])} ({_e(o['when'])})" for o in d["order"]),
        ]
    elif kind == "quote":
        lines.append(f"<b>{_e(d['price'])}</b> ({_e(d['change_text'])} today)")
        if "return_1y" in d:
            lines.append(
                f"1 year: {_e(d['return_1y'])}, swings {_e(d['volatility'])}, "
                f"worst fall {_e(d['worst_fall'])}"
            )
    elif kind == "watchlist":
        lines += [f"{_e(r['symbol'])}: {_e(r['price'])} {_e(r['change_text'])}" for r in d["rows"]]
    elif kind == "news":
        lines += [
            f'{i}. <a href="{_e(n["link"])}">{_e(n["title"])}</a>'
            + (
                f" ({_e(n['source'])}{', ' + _e(n['date']) if n.get('date') else ''})"
                if n.get("source")
                else ""
            )
            for i, n in enumerate(d["items"], 1)
        ]
    elif kind == "todo":
        lines += [f"• {_e(item['text'])}" for item in d["items"]]
    elif kind == "options":
        lines += [f"• {_e(r['label'])}: {_e(r['value'])}" for r in d["rows"]]
    if card.get("outcome"):
        lines.append(f"<i>{_e(card['outcome'])}</i>")
    return "\n".join(lines)


def render_message(msg: ChatMessage) -> tuple[str, list[list[tuple[str, str]]]]:
    """HTML text plus button rows of (label, callback_data)."""
    m = CREW.get(msg.author, CREW["finbo"])
    header = f"{m.emoji} <b>{_e(m.name)}</b>"
    contributors = [CREW[c].name for c in msg.meta.get("contributors", []) if c in CREW]
    if contributors:
        header += f" <i>with {_e(' and '.join(contributors))}</i>"
    parts = [header]
    if msg.meta.get("note"):
        parts.append(f"<i>{_e(msg.meta['note'])}</i>")
    parts.append(_e(msg.text))
    unverified = (msg.meta.get("checks") or {}).get("unverified_figures") or []
    if unverified:
        parts.append(
            "<i>Check these figures, I couldn’t trace them to a calculation: "
            f"{_e(', '.join(unverified))}</i>"
        )
    parts += [render_card(c) for c in msg.cards]
    text = "\n\n".join(parts)
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1] + "…"

    rows: list[list[tuple[str, str]]] = []
    for ci, card in enumerate(msg.cards):
        buttons = [(a["label"], f"a:{msg.id}:{ci}:{ai}") for ai, a in enumerate(card["actions"])]
        for i in range(0, len(buttons), 2):
            rows.append(buttons[i : i + 2])
    return text, rows


def quick_rows(crew_id: str) -> list[list[tuple[str, str]]]:
    return [
        [(a.label, f"q:{crew_id}:{a.id}")] for a in CREW[crew_id].quick_actions if a.needs is None
    ]


def crew_text() -> str:
    lines = ["<b>Meet the crew</b>. Talk to anyone with their command:"]
    for m in CREW.values():
        lines.append(f"{m.emoji} /{m.id}: <b>{_e(m.name)}</b>, {_e(m.role.lower())}")
    lines.append("\nExample: <code>/snowy when will I be debt-free?</code>")
    return "\n".join(lines)


HELP = (
    "Talk to the crew with /finbo, /penny, /hazel, /snowy, /bruno or /scout, then just type. "
    "Send a bank statement as a .csv file to use your own numbers.\n\n"
    "/crew who does what\n/link CODE connect your Finbo web account\n/unlink stop sharing\n"
    "/reset delete your data here\n\nFinbo gives educational guidance, not regulated advice."
)


# ---------- the bot ----------


class FinboBot:
    """Handlers take duck-typed update/context objects, so they can be tested without
    a real Telegram connection."""

    def __init__(self, store: Store, service: ChatService) -> None:
        self.store = store
        self.service = service

    def _uid(self, update) -> str:
        return user_id_for(self.store, update.effective_user.id)

    async def _send(self, target, msg: ChatMessage) -> None:
        text, rows = render_message(msg)
        await target.reply_text(
            text, parse_mode="HTML", reply_markup=_markup(rows), disable_web_page_preview=True
        )

    async def _send_all(self, target, messages: list[ChatMessage]) -> None:
        for m in messages:
            if m.role == "agent":
                await self._send(target, m)

    async def _setup_prompt(self, target) -> None:
        await target.reply_text(
            "Hi, I’m Finbo 🦊. Let’s set you up. Pick a country to start with sample numbers, "
            "or send me your bank statement as a .csv file.",
            reply_markup=_markup([[("India (₹)", "setup:in"), ("United States ($)", "setup:us")]]),
        )

    async def start(self, update, context) -> None:
        args = list(getattr(context, "args", None) or [])
        if args and args[0].startswith("link-"):
            context.args = [args[0][5:]]
            await self.link(update, context)
            return
        if self.store.load_workspace(self._uid(update)) is None:
            await self._setup_prompt(update.message)
            return
        await update.message.reply_text(crew_text(), parse_mode="HTML")

    async def crew(self, update, context) -> None:
        await update.message.reply_text(crew_text(), parse_mode="HTML")

    async def help(self, update, context) -> None:
        await update.message.reply_text(HELP)

    async def talk(self, update, context, crew_id: str) -> None:
        """/penny [question]"""
        context.user_data["agent"] = crew_id
        text = " ".join(getattr(context, "args", None) or []).strip()
        if text:
            await self._chat(update, crew_id, text)
            return
        m = CREW[crew_id]
        await update.message.reply_text(
            f"{m.emoji} <b>{_e(m.name)}</b>\n{_e(m.greeting)}",
            parse_mode="HTML",
            reply_markup=_markup(quick_rows(crew_id)),
        )

    async def text(self, update, context) -> None:
        crew_id = context.user_data.get("agent", "finbo")
        await self._chat(update, crew_id, update.message.text or "")

    async def _chat(self, update, crew_id: str, text: str) -> None:
        if not text.strip():
            return
        await _typing(update)
        try:
            messages = await self.service.send(
                self._uid(update), crew_id, text[:1000], channel="telegram"
            )
        except NotSetUp:
            await self._setup_prompt(update.message)
            return
        await self._send_all(update.message, messages)

    async def link(self, update, context) -> None:
        args = list(getattr(context, "args", None) or [])
        if not args:
            await update.message.reply_text(
                "Open Finbo on the web, go to Settings, choose “Connect Telegram” and send me the "
                "code like this: /link ABCD2345"
            )
            return
        user_id = self.store.redeem_link_code(
            args[0].strip().upper(), str(update.effective_user.id)
        )
        if user_id is None:
            await update.message.reply_text(
                "That code didn’t work. Codes last 10 minutes; get a fresh one in Settings."
            )
            return
        await update.message.reply_text(
            "Linked 🦊 Telegram and the web app now share your money data, plans and chats."
        )

    async def unlink(self, update, context) -> None:
        self.store.unlink_telegram(str(update.effective_user.id))
        await update.message.reply_text("Unlinked. Telegram is back to its own separate data.")

    async def reset(self, update, context) -> None:
        await update.message.reply_text(
            "Delete your Finbo data in this chat (statement, plans, chats)? If this chat is linked "
            "to a web account, it will only be unlinked. This can’t be undone.",
            reply_markup=_markup([[("Yes, delete it", "reset:yes"), ("Keep it", "reset:no")]]),
        )

    async def document(self, update, context) -> None:
        doc = update.message.document
        if not (doc.file_name or "").lower().endswith(".csv"):
            await update.message.reply_text(
                "Send your statement as a .csv file (Date, Category, Amount)."
            )
            return
        if (doc.file_size or 0) > MAX_CSV_BYTES:
            await update.message.reply_text(
                "That file is over 1 MB. Send one statement period at a time."
            )
            return
        uid = self._uid(update)
        ws = self.store.load_workspace(uid)
        if ws is None:
            await self._setup_prompt(update.message)
            return
        data = bytes(await (await doc.get_file()).download_as_bytearray())
        try:
            result = parse_transactions_csv(data.decode("utf-8-sig"), ws.finance.profile.currency)
        except (UnicodeDecodeError, CsvSchemaError) as e:
            await update.message.reply_text(f"I couldn’t read that file: {e}")
            return
        if result.errors:
            first = "\n".join(f"Line {e.line}, {e.column}: {e.message}" for e in result.errors[:5])
            await update.message.reply_text(f"Some rows need fixing first:\n{first}")
            return
        ws.finance.transactions = result.transactions
        ws.finance.bucket_overrides.clear()
        ws.transactions_source = "uploaded"
        self.store.save_workspace(uid, ws)
        await update.message.reply_text(
            f"Got {len(result.transactions)} transactions 🐧 Penny has your new numbers.",
            reply_markup=_markup(quick_rows("penny")),
        )

    async def button(self, update, context) -> None:
        query = update.callback_query
        await query.answer()
        uid = self._uid(update)
        kind, _, rest = (query.data or "").partition(":")
        target = query.message
        try:
            if kind == "setup":
                # Only ever creates a workspace; never replaces one (a linked web account's
                # data must not be overwritten from Telegram).
                if self.store.load_workspace(uid) is not None:
                    await target.reply_text("You’re already set up. Ask the crew anything.")
                    return
                market = "us" if rest == "us" else "in"
                self.store.save_workspace(
                    uid, Workspace(market=market, finance=FinanceSession.sample(market))
                )
                await target.reply_text(
                    "You’re set up with sample numbers. "
                    "Send a .csv statement any time to use your own.\n\n" + crew_text(),
                    parse_mode="HTML",
                    reply_markup=_markup(quick_rows("finbo")),
                )
            elif kind == "reset":
                if rest == "yes":
                    if uid.startswith("tg:"):
                        self.store.delete_user(uid)
                        await target.reply_text(
                            "Deleted. Send /start whenever you want to begin again."
                        )
                    else:
                        # Linked to a web account: only unlink here; web data is managed on the web.
                        self.store.unlink_telegram(str(update.effective_user.id))
                        await target.reply_text(
                            "Unlinked this chat. Your web account’s data is untouched; delete it "
                            "from Settings on the web if you want it gone."
                        )
                else:
                    await target.reply_text("Kept everything as it was.")
            elif kind == "q":
                crew_id, _, action = rest.partition(":")
                context.user_data["agent"] = crew_id
                await self._send_all(
                    target, await self.service.quick(uid, crew_id, action, channel="telegram")
                )
            elif kind == "a":
                message_id, card, action = (int(x) for x in rest.split(":"))
                await self._send_all(
                    target,
                    await self.service.act(uid, message_id, card, action, channel="telegram"),
                )
        except NotSetUp:
            await self._setup_prompt(target)
        except (UnknownAction, ValueError):
            await target.reply_text("That button has expired. Ask again and I’ll make a fresh one.")


def _markup(rows: list[list[tuple[str, str]]]):
    if not rows:
        return None
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


async def _typing(update) -> None:
    # Cosmetic only: never fail a reply because the typing indicator didn't send.
    with contextlib.suppress(Exception):
        await update.effective_chat.send_action("typing")


def build_application(token: str, store: Store, service: ChatService):
    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    bot = FinboBot(store, service)
    app = Application.builder().token(token).post_init(set_commands).build()
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help))
    app.add_handler(CommandHandler("crew", bot.crew))
    app.add_handler(CommandHandler("link", bot.link))
    app.add_handler(CommandHandler("unlink", bot.unlink))
    app.add_handler(CommandHandler("reset", bot.reset))
    for crew_id in CREW:
        app.add_handler(CommandHandler(crew_id, lambda u, c, cid=crew_id: bot.talk(u, c, cid)))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.text))
    app.add_handler(CallbackQueryHandler(bot.button))
    return app


async def set_commands(app) -> None:
    from telegram import BotCommand

    commands = [BotCommand(m.id, f"{m.name}: {m.role}") for m in CREW.values()]
    commands += [
        BotCommand("crew", "Who does what"),
        BotCommand("link", "Connect your web account"),
        BotCommand("help", "How Finbo works"),
    ]
    await app.bot.set_my_commands(commands)
