"""Chat with Finbo's crew, shared by the web app and the Telegram bot.

Three ways a reply is produced:
- quick actions: each crew member answers its starter questions straight from the
  calculation engine (no LLM, so they work without any key and never invent numbers);
- AI chat: free text goes through the guarded agent run (copilot.ask_copilot);
- offline routing: without an LLM key, free text is matched to the closest quick action,
  and the reply says so.

Replies carry cards (debt plan, safety net, spending, quote, news...) built from tool
results, never from LLM text. Card buttons are executed by looking the action up in the
stored message, so an approval can't be forged by a client.
"""

from __future__ import annotations

import json
import re
import uuid
from calendar import month_abbr
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from . import research
from .calc import calculations
from .copilot import ask_copilot
from .core import Currency, format_amount
from .crew import CREW
from .excel import debt_subject, proposals
from .guardrails import DISCLAIMER, redact, scan
from .llm import AllProvidersFailedError, NoProviderConfiguredError, configured_providers
from .market import (
    InvalidSymbolError,
    MarketDataError,
    MarketDataProvider,
    default_provider,
    history_stats,
    resolve_symbol,
)
from .store import Approval, ChatMessage, Store, Workspace
from .tools import build_personal_tools

STEP = {"in": 5000, "us": 300}  # the "try a bit more" amount for debt payments


class NotSetUp(LookupError):
    pass


class UnknownAction(LookupError):
    pass


# ---------- formatting (server-side, so web and Telegram show identical numbers) ----------


def money(value: Any, currency: str, whole: bool = True) -> str:
    d = Decimal(str(value))
    if whole:
        d = d.quantize(Decimal(1), rounding=ROUND_HALF_UP)
    text = format_amount(d, Currency(currency))
    return text[:-3] if whole and text.endswith(".00") else text


def pct(value: Any, digits: int = 1) -> str:
    return f"{Decimal(str(value)):.{digits}f}%"


def month_label(months_ahead: int, today: date | None = None) -> str:
    today = today or date.today()
    m = today.month - 1 + months_ahead
    return f"{month_abbr[m % 12 + 1]} {today.year + m // 12}"


def _action(kind: str, label: str, **payload: Any) -> dict[str, Any]:
    return {"kind": kind, "label": label, "payload": payload}


def _card(kind: str, title: str, data: dict[str, Any], actions: list | None = None) -> dict:
    return {"kind": kind, "title": title, "data": data, "actions": actions or []}


# ---------- reusable card builders ----------


def spending_card(calc: dict[str, Any]) -> dict:
    s, cur = calc["spending"], calc["currency"]
    buckets = {b["bucket"]: b for b in s["buckets"]}
    rows = []
    for key, label, guide in (
        ("needs", "Needs", "up to 50%"),
        ("wants", "Wants", "up to 30%"),
        ("savings", "Kept", "at least 20%"),
    ):
        b = buckets.get(key)
        if b:
            rows.append(
                {
                    "label": label,
                    "amount": money(b["monthly_avg"], cur),
                    "pct": float(b["pct_of_income"] or 0),
                    "pct_text": pct(b["pct_of_income"] or 0, 0),
                    "guide": guide,
                }
            )
    return _card(
        "spending",
        "Where your money goes each month",
        {
            "income": money(s["monthly_income"], cur),
            "spending": money(s["avg_monthly_spending"], cur),
            "rows": rows,
            "top": [
                {"category": c["category"], "amount": money(c["monthly_avg"], cur)}
                for c in s["categories"][:5]
            ],
        },
    )


def safety_card(result: dict[str, Any], currency: str) -> dict:
    p = result["plan"]
    target = Decimal(p["target_amount"])
    have = Decimal(p["current_balance"])
    return _card(
        "safety",
        "Your safety net",
        {
            "have": money(have, currency),
            "target": money(target, currency),
            "gap": money(p["gap"], currency),
            "progress": float(min(have / target, Decimal(1))) if target else 1.0,
            "target_months": p["target_months"],
            "covered_months": p["coverage_months"],
            "monthly": money(p["monthly_contribution"], currency),
            "months_to_target": p["months_to_target"],
            "funded": p["is_funded"],
        },
    )


def debt_card(result: dict[str, Any], currency: str) -> dict | None:
    if "comparison" not in result:
        return None
    c = result["comparison"]
    best = c[c["cheapest"]]
    extra = Decimal(result["monthly_budget"]) - Decimal(result["sum_of_minimums"])
    return _card(
        "debt",
        "Your way out of debt",
        {
            "method": c["cheapest"],
            "monthly": money(result["monthly_budget"], currency),
            "minimums": money(result["sum_of_minimums"], currency),
            "extra": money(extra, currency),
            "months": best["months"],
            "debt_free": month_label(best["months"]),
            "interest": money(best["total_interest"], currency),
            "saved_vs_other": money(c["interest_saved_with_avalanche"], currency),
            "first_win_sooner": c["earlier_first_win_with_snowball"],
            "order": [
                {
                    "name": d["name"],
                    "month": d["month_paid_off"],
                    "when": month_label(d["month_paid_off"]),
                }
                for d in best["payoff_order"]
            ],
        },
    )


def quote_card(quote: dict[str, Any], stats: dict[str, Any] | None) -> dict:
    cur = quote["currency"]
    data = {
        "symbol": quote["symbol"],
        "name": quote.get("name") or quote["symbol"],
        "price": _price(quote["price"], cur),
        "change": float(quote["change_pct"] or 0),
        "change_text": _signed(quote["change_pct"]),
        "year_low": _price(quote["year_low"], cur) if quote.get("year_low") else None,
        "year_high": _price(quote["year_high"], cur) if quote.get("year_high") else None,
    }
    if stats:
        data |= {
            "return_1y": _signed(stats["return_pct"], 1),
            "volatility": pct(stats["annualised_volatility_pct"] or 0),
            "worst_fall": _signed(stats["max_drawdown_pct"], 1),
        }
    return _card("quote", data["name"], data)


def news_card(items: list[dict[str, Any]], title: str) -> dict:
    return _card(
        "news",
        title,
        {
            "items": [
                {
                    "title": i["title"],
                    "source": i.get("source"),
                    "link": i["link"],
                    "date": _short_date(i.get("published")),
                }
                for i in items[:5]
            ]
        },
    )


def _price(value: Any, currency: str) -> str:
    if currency in ("INR", "USD"):
        return money(value, currency, whole=False)
    return f"{Decimal(str(value)):,.2f} {currency}"


def _signed(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    d = Decimal(str(value))
    body = f"{abs(d):.{digits}f}%"
    return f"+{body}" if d > 0 else (f"−{body}" if d < 0 else body)


def _short_date(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return f"{d.day} {month_abbr[d.month]}"


def _safe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in items if not scan(i["title"], use_model=False).flagged]


# ---------- quick actions (no LLM) ----------


@dataclass
class Ctx:
    ws: Workspace
    store: Store
    user_id: str
    market_data: MarketDataProvider
    arg: str | None

    @property
    def currency(self) -> str:
        return self.ws.finance.profile.currency.value


QuickFn = Callable[[Ctx], tuple[str, list[dict]]]


def _approved(ctx: Ctx, subject: str) -> bool:
    return any(a.subject == subject for a in ctx.store.list_approvals(ctx.user_id))


def _plan_actions(ctx: Ctx, subject: str) -> list[dict]:
    if _approved(ctx, subject):
        return []
    return [
        _action("approve", "Approve this plan", subject=subject),
        _action("send_back", "Not now", subject=subject),
    ]


def q_glance(ctx: Ctx) -> tuple[str, list[dict]]:
    calc = calculations(ctx.ws.market, ctx.ws.finance)
    s, cur = calc["spending"], ctx.currency
    p = calc["emergency_fund"]["plan"]
    left = Decimal(s["avg_monthly_savings"])
    debt = calc["debt"]
    if "comparison" in debt:
        best = debt["comparison"][debt["comparison"]["cheapest"]]
        debt_line = (
            f"Paying just the minimums, you’d be debt-free by {month_label(best['months'])}."
        )
        debt_free = month_label(best["months"])
    else:
        debt_line, debt_free = "You have no debts. Lovely.", "No debts"
    text = (
        f"Here’s your month. You have about {money(left, cur)} left after spending, which is "
        f"{pct(s['savings_rate_pct'] or 0, 0)} of your income. Your safety net covers "
        f"{p['coverage_months'] or 0} of the {p['target_months']} months it should. {debt_line}"
    )
    card = _card(
        "summary",
        "Your month at a glance",
        {
            "left_over": money(left, cur),
            "savings_rate": pct(s["savings_rate_pct"] or 0, 0),
            "safety": f"{p['coverage_months'] or 0} of {p['target_months']} months",
            "debt_free": debt_free,
        },
        [
            _action("quick", "What needs my attention?", agent="finbo", action="attention"),
        ],
    )
    return text, [card]


def q_attention(ctx: Ctx) -> tuple[str, list[dict]]:
    calc = calculations(ctx.ws.market, ctx.ws.finance)
    items: list[dict] = []
    for category in calc["spending"]["unclassified_categories"]:
        items.append(
            {
                "text": f"Penny needs you to sort “{category}” into needs, wants or savings.",
                "action": _action("quick", "Sort it with Penny", agent="penny", action="file"),
            }
        )
    for proposal in proposals(calc):
        if not _approved(ctx, proposal.subject):
            who, action = (
                ("snowy", "debt_free")
                if proposal.subject.startswith("Debt")
                else ("hazel", "safety_net")
            )
            items.append(
                {
                    "text": f"{CREW[who].name} has a plan waiting for your OK.",
                    "action": _action(
                        "quick", f"See {CREW[who].name}’s plan", agent=who, action=action
                    ),
                }
            )
    if ctx.ws.transactions_source == "sample":
        items.append(
            {
                "text": "These numbers come from sample data. "
                "Upload your own statement to make them yours."
            }
        )
    if not items:
        return "Nothing needs you right now. Everything is sorted and every plan is signed off.", []
    # Buttons must live in the card's action list (that's what act() executes);
    # each item points at its button by index.
    actions = []
    for item in items:
        action = item.pop("action", None)
        if action:
            item["action_index"] = len(actions)
            actions.append(action)
    text = f"{len(items)} thing{'s' if len(items) != 1 else ''} could use your attention:"
    return text, [_card("todo", "Waiting on you", {"items": items}, actions)]


def q_spending(ctx: Ctx) -> tuple[str, list[dict]]:
    calc = calculations(ctx.ws.market, ctx.ws.finance)
    s, cur = calc["spending"], ctx.currency
    buckets = {b["bucket"]: b for b in s["buckets"]}
    top = [c["category"] for c in s["categories"] if c["bucket"] != "savings"][:3]
    needs = buckets["needs"]["pct_of_income"] or 0
    wants = buckets["wants"]["pct_of_income"] or 0
    kept = s["savings_rate_pct"] or 0
    verdict = (
        "That’s a healthy split."
        if Decimal(needs) <= 50 and Decimal(wants) <= 30 and Decimal(kept) >= 20
        else "There’s room to rebalance."
    )
    text = (
        f"You spend about {money(s['avg_monthly_spending'], cur)} a month. Needs take "
        f"{pct(needs, 0)} of your income, wants {pct(wants, 0)}, and you keep {pct(kept, 0)}. "
        f"{verdict} Your biggest costs are {', '.join(top[:-1])} and {top[-1]}."
    )
    card = spending_card(calc)
    if s["unclassified_categories"]:
        card["actions"].append(
            _action("quick", "Sort the unfiled ones", agent="penny", action="file")
        )
    return text, [card]


def q_file(ctx: Ctx) -> tuple[str, list[dict]]:
    calc = calculations(ctx.ws.market, ctx.ws.finance)
    unfiled = [c for c in calc["spending"]["categories"] if c["bucket"] == "unclassified"]
    if not unfiled:
        return "Everything is filed. Nice and tidy.", []
    cards = [
        _card(
            "file",
            f"{c['category']}: {money(c['monthly_avg'], ctx.currency)} a month",
            {"category": c["category"]},
            [
                _action("file", label, category=c["category"], bucket=bucket)
                for label, bucket in (("Need", "needs"), ("Want", "wants"), ("Savings", "savings"))
            ],
        )
        for c in unfiled
    ]
    return (
        "I don’t guess where unfamiliar spending belongs. Is this a need, a want or savings?",
        cards,
    )


def q_safety_net(ctx: Ctx) -> tuple[str, list[dict]]:
    calc = calculations(ctx.ws.market, ctx.ws.finance)
    result = calc["emergency_fund"]
    p, prof = result["plan"], ctx.ws.finance.profile
    why = (
        "steady income"
        if prof.income_stability == "stable"
        else "income that changes month to month"
    )
    why += (
        " and no dependents"
        if prof.dependents == 0
        else f" and {prof.dependents} dependent{'s' if prof.dependents > 1 else ''}"
    )
    card = safety_card(result, ctx.currency)
    if p["is_funded"]:
        return (
            f"Your safety net is full: {p['target_months']} months of essentials. "
            "Anything extra can go to debts or goals.",
            [card],
        )
    for proposal in proposals(calc):
        if proposal.subject.startswith("Safety net"):
            card["actions"] = _plan_actions(ctx, proposal.subject)
    card["actions"].append(
        _action("quick", "How fast can I fill it?", agent="hazel", action="faster")
    )
    text = (
        f"Aim for {p['target_months']} months of essentials, "
        f"{money(p['target_amount'], ctx.currency)}, "
        f"because you have {why}. You have {money(p['current_balance'], ctx.currency)}, so "
        f"{money(p['gap'], ctx.currency)} to go. Setting aside "
        f"{money(p['monthly_contribution'], ctx.currency)} a month gets you there in about "
        f"{p['months_to_target']} months."
    )
    return text, [card]


def q_faster(ctx: Ctx) -> tuple[str, list[dict]]:
    tools = build_personal_tools(ctx.ws.finance)
    surplus = max(Decimal(ctx.ws.finance.budget_report().avg_monthly_savings), Decimal(0))
    if surplus == 0:
        return (
            "There’s nothing left over each month yet, so let’s look at spending first with Penny.",
            [],
        )
    rows = []
    for share, label in (
        (Decimal("0.25"), "A quarter"),
        (Decimal("0.5"), "Half"),
        (Decimal(1), "All"),
    ):
        amount = (surplus * share).quantize(Decimal(1))
        plan = tools["plan_emergency_fund"].func(monthly_contribution=float(amount))["plan"]
        months = plan["months_to_target"]
        rows.append(
            {
                "label": f"{label} of what’s left: {money(amount, ctx.currency)} a month",
                "value": "Already full"
                if plan["is_funded"]
                else f"{months} months ({month_label(months)})",
            }
        )
    return "Here’s how the timing changes with how much you put away each month:", [
        _card("options", "Filling your safety net", {"rows": rows})
    ]


def _debt_reply(ctx: Ctx, extra: Decimal) -> tuple[dict | None, dict, list]:
    calc = calculations(ctx.ws.market, ctx.ws.finance, extra_debt_payment=float(extra))
    return debt_card(calc["debt"], ctx.currency), calc, proposals(calc)


def q_debt_free(ctx: Ctx) -> tuple[str, list[dict]]:
    extra = Decimal(ctx.arg or 0)
    card, calc, props = _debt_reply(ctx, extra)
    if card is None:
        return calc["debt"].get("message") or calc["debt"].get("error") or "No debt plan.", []
    d = card["data"]
    subject = next(p.subject for p in props if p.subject.startswith("Debt"))
    card["actions"] = _plan_actions(ctx, subject)
    step = STEP[ctx.ws.market] if extra == 0 else int(extra) * 2
    card["actions"].append(
        _action(
            "quick",
            f"Try {money(step, ctx.currency)} extra a month",
            agent="snowy",
            action="debt_free",
            arg=str(step),
        )
    )
    paying = f"{d['monthly']} a month" + (
        f" ({d['minimums']} minimums plus {d['extra']} extra)" if extra else " (just the minimums)"
    )
    text = (
        f"Paying {paying}, you’d be debt-free in {d['months']} months, around {d['debt_free']}. "
        f"The {d['method']} method costs {d['interest']} in interest along the way."
    )
    return text, [card]


def q_compare(ctx: Ctx) -> tuple[str, list[dict]]:
    extra = Decimal(ctx.arg or STEP[ctx.ws.market])
    card, calc, _ = _debt_reply(ctx, extra)
    if card is None:
        return calc["debt"].get("message") or calc["debt"].get("error") or "No debt plan.", []
    c = calc["debt"]["comparison"]
    saved = Decimal(c["interest_saved_with_avalanche"])
    sooner = c["earlier_first_win_with_snowball"]
    text = (
        f"With {money(extra, ctx.currency)} extra a month: avalanche (highest interest first) "
        f"saves {money(saved, ctx.currency)} in interest. "
        + (
            f"Snowball (smallest balance first) clears your first debt {sooner} month"
            f"{'s' if sooner != 1 else ''} sooner, which some people find motivating."
            if sooner > 0
            else "Snowball gives you no earlier win here, so avalanche is the clear pick."
        )
    )
    return text, [card]


def q_watchlist(ctx: Ctx) -> tuple[str, list[dict]]:
    if not ctx.ws.watchlist:
        examples = ["RELIANCE", "^NSEI"] if ctx.ws.market == "in" else ["AAPL", "^GSPC"]
        return (
            "Your watchlist is empty. Tell me a ticker and I’ll check it, or try one of these.",
            [
                _card(
                    "actions",
                    "Try a stock",
                    {},
                    [
                        _action("quick", f"Check {e}", agent="bruno", action="check", arg=e)
                        for e in examples
                    ],
                )
            ],
        )
    rows = []
    for symbol in ctx.ws.watchlist:
        try:
            q = ctx.market_data.quote(symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "price": _price(q.price, q.currency),
                    "change_text": _signed(q.change_pct),
                    "change": float(q.change_pct or 0),
                }
            )
        except MarketDataError:
            rows.append({"symbol": symbol, "price": "No price", "change_text": "", "change": 0})
    return "Here’s your watchlist. Prices are delayed from Yahoo Finance.", [
        _card("watchlist", "Your watchlist", {"rows": rows})
    ]


def q_check(ctx: Ctx) -> tuple[str, list[dict]]:
    if not ctx.arg:
        return "Which stock? Send a ticker like RELIANCE, TCS, AAPL or ^NSEI.", []
    try:
        symbol = resolve_symbol(ctx.arg, ctx.ws.market, ctx.market_data)
        quote = ctx.market_data.quote(symbol)
    except (InvalidSymbolError, MarketDataError):
        return (
            f"I couldn’t find {ctx.arg.strip().upper()} on NSE, BSE or US exchanges. "
            "Check the ticker?",
            [],
        )
    try:
        stats = history_stats(symbol, "1y", ctx.market_data.history(symbol, "1y")).model_dump(
            mode="json"
        )
    except (MarketDataError, ValueError):
        stats = None
    card = quote_card(quote.model_dump(mode="json"), stats)
    d = card["data"]
    direction = "up" if d["change"] > 0 else ("down" if d["change"] < 0 else "flat")
    text = f"{d['name']} is at {d['price']}, {direction} {d['change_text'].lstrip('+−')} today."
    if stats:
        text += (
            f" Over the past year it’s {d['return_1y']}, it typically swings about "
            f"{d['volatility']} "
            f"a year, and its worst fall was {d['worst_fall']}. Money you need within a couple of "
            "years usually stays out of anything that can drop like that."
        )
    if symbol not in ctx.ws.watchlist:
        card["actions"].append(_action("watch", "Add to my watchlist", symbol=symbol))
    return text, [card]


def q_headlines(ctx: Ctx) -> tuple[str, list[dict]]:
    try:
        items = _safe([i.model_dump(mode="json") for i in research.market_headlines(ctx.ws.market)])
    except research.ResearchError as e:
        return f"I couldn’t reach the news feeds just now ({e}). Try again in a minute.", []
    return (
        "Here’s what the market news is saying today. Tap a headline to read it at the source.",
        [news_card(items, "Market headlines")],
    )


def q_news(ctx: Ctx) -> tuple[str, list[dict]]:
    if not ctx.arg:
        return "News about what? Send a company or topic, like Infosys or interest rates.", []
    try:
        items = _safe(
            [i.model_dump(mode="json") for i in research.search_news(ctx.arg, ctx.ws.market)]
        )
    except research.ResearchError as e:
        return f"I couldn’t reach the news feeds just now ({e}). Try again in a minute.", []
    if not items:
        return f"I didn’t find recent news about {ctx.arg}.", []
    return f"Here’s the latest on {ctx.arg}, with the source for each.", [
        news_card(items, f"News: {ctx.arg}")
    ]


QUICK: dict[tuple[str, str], QuickFn] = {
    ("finbo", "glance"): q_glance,
    ("finbo", "attention"): q_attention,
    ("penny", "spending"): q_spending,
    ("penny", "file"): q_file,
    ("hazel", "safety_net"): q_safety_net,
    ("hazel", "faster"): q_faster,
    ("snowy", "debt_free"): q_debt_free,
    ("snowy", "compare"): q_compare,
    ("bruno", "watchlist"): q_watchlist,
    ("bruno", "check"): q_check,
    ("scout", "headlines"): q_headlines,
    ("scout", "news"): q_news,
}

# Without an LLM, free text is matched to the closest quick action.
_INTENTS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"(?i)\b(avalanche|snowball)\b"), "snowy", "compare"),
    (re.compile(r"(?i)\b(debt|loan|emi|credit card|card bill|pay ?off|owe)"), "snowy", "debt_free"),
    (re.compile(r"(?i)\b(emergency|safety net|rainy day|fill it|faster)"), "hazel", "safety_net"),
    (
        re.compile(r"(?i)\b(spend|spent|budget|expense|cut back|where.*money|categor)"),
        "penny",
        "spending",
    ),
    (re.compile(r"(?i)\b(headline|news|happening)"), "scout", "headlines"),
    (re.compile(r"(?i)\b(watchlist|stock|share|nifty|sensex|market|price)"), "bruno", "watchlist"),
    (re.compile(r"(?i)\b(save|saving)"), "hazel", "safety_net"),
    (re.compile(r"(?i)\b(attention|todo|to do|pending|waiting)"), "finbo", "attention"),
]
_TICKER = re.compile(r"^\^?[A-Za-z0-9.&=\-]{1,20}$")


def route_offline(thread: str, text: str) -> tuple[str, str, str | None]:
    """(agent, action, arg) for free text when no LLM is available."""
    words = text.strip()
    if thread == "bruno" and _TICKER.match(words):
        return "bruno", "check", words
    if thread == "scout" and len(words) < 60 and not words.endswith("?"):
        return "scout", "news", words
    for pattern, agent, action in _INTENTS:
        if pattern.search(text) and (thread == "finbo" or agent == thread):
            return agent, action, None
    member = CREW[thread]
    first = member.quick_actions[0]
    if first.needs is None:
        return thread, first.id, None
    return "finbo", "glance", None


# ---------- AI replies: cards from the tools the agents actually called ----------


def _cards_from_trace(trace: list, currency: str) -> list[dict]:
    by_kind: dict[str, dict] = {}
    quote: dict | None = None
    stats: dict | None = None
    for call in trace:
        if not call.ok or not call.result:
            continue
        try:
            data = json.loads(call.result)
        except ValueError:
            continue
        if not isinstance(data, dict) or "error" in data:
            continue
        if call.name == "compare_debt_strategies":
            card = debt_card(data, currency)
            if card:
                card["subject"] = debt_subject(data, currency)  # same name as everywhere else
                by_kind["debt"] = card
        elif call.name == "plan_emergency_fund":
            by_kind["safety"] = safety_card(data, currency)
        elif call.name == "get_quote":
            quote = data
        elif call.name == "get_price_history_stats":
            stats = data
        elif call.name in ("search_news", "market_headlines") and data.get("items"):
            by_kind["news"] = news_card(data["items"], "From the news")
    if quote:
        by_kind["quote"] = quote_card(quote, stats)
    return list(by_kind.values())


# ---------- the service ----------


class ChatService:
    def __init__(
        self,
        store: Store,
        market_data: Callable[[], MarketDataProvider] = default_provider,
        providers: Callable[[], list] = configured_providers,
    ) -> None:
        self.store = store
        self._market_data = market_data
        self._providers = providers

    def _ws(self, user_id: str) -> Workspace:
        ws = self.store.load_workspace(user_id)
        if ws is None:
            raise NotSetUp(user_id)
        return ws

    def history(self, user_id: str, thread: str, limit: int = 60) -> list[ChatMessage]:
        CREW[thread]  # validates the thread
        return self.store.list_messages(user_id, thread, limit)

    def _reply(
        self,
        user_id: str,
        thread: str,
        author: str,
        text: str,
        cards: list,
        channel: str,
        **meta: Any,
    ) -> ChatMessage:
        return self.store.add_message(user_id, thread, "agent", author, text, cards, meta, channel)

    async def quick(
        self, user_id: str, thread: str, action: str, arg: str | None = None, channel: str = "web"
    ) -> list[ChatMessage]:
        fn = QUICK.get((thread, action))
        if fn is None:
            raise UnknownAction(f"{thread}/{action}")
        ws = self._ws(user_id)
        label = next(a.label for a in CREW[thread].quick_actions if a.id == action)
        if arg:
            label = f"{label}: {arg}"
        asked = self.store.add_message(user_id, thread, "user", "you", label, channel=channel)
        text, cards = fn(Ctx(ws, self.store, user_id, self._market_data(), arg))
        return [asked, self._reply(user_id, thread, thread, text, cards, channel, mode="quick")]

    async def send(
        self, user_id: str, thread: str, text: str, channel: str = "web"
    ) -> list[ChatMessage]:
        CREW[thread]
        ws = self._ws(user_id)
        shown = redact(text).text  # chat history keeps the redacted text, like the audit log
        # Earlier turns go back to the model without the appended disclaimer.
        prior = [
            (m.role, m.text.replace(f"\n\n{DISCLAIMER}", ""))
            for m in self.store.list_messages(user_id, thread, 20)
        ]
        asked = self.store.add_message(user_id, thread, "user", "you", shown, channel=channel)

        try:
            providers = self._providers()
        except NoProviderConfiguredError:
            providers = []
        if not providers:
            agent, action, arg = route_offline(thread, text)
            reply_text, cards = QUICK[(agent, action)](
                Ctx(ws, self.store, user_id, self._market_data(), arg)
            )
            note = (
                f"Free chat needs an AI key on the server, so {CREW[agent].name} answered the "
                "closest question instead."
            )
            return [
                asked,
                self._reply(
                    user_id, thread, agent, reply_text, cards, channel, mode="offline", note=note
                ),
            ]

        try:
            result = await ask_copilot(
                text, ws.finance, providers, self._market_data(), agent=thread, history=prior
            )
        except AllProvidersFailedError:
            return [
                asked,
                self._reply(
                    user_id,
                    thread,
                    thread,
                    "The AI service didn’t answer just now. "
                    "Try again in a minute, or tap a quick question.",
                    [],
                    channel,
                    mode="error",
                ),
            ]
        contributors = sorted({c.name for c in result.trace if c.name in CREW and c.name != thread})
        self.store.add_event(
            user_id,
            "refused" if result.checks.refused else "ask",
            result.question_sent or "[question not sent to the AI]",
            {
                "answer": result.answer,
                "agent": thread,
                "checks": result.checks.as_dict(),
                "provider": result.provider,
            },
        )
        cards = (
            []
            if result.checks.refused
            else _cards_from_trace(result.trace, ws.finance.profile.currency.value)
        )
        ctx = Ctx(ws, self.store, user_id, self._market_data(), None)
        for card in cards:
            subject = card.pop("subject", None)
            if subject:
                card["actions"] = _plan_actions(ctx, subject)
        return [
            asked,
            self._reply(
                user_id,
                thread,
                thread,
                result.answer,
                cards,
                channel,
                mode="ai",
                contributors=contributors,
                checks=result.checks.as_dict(),
                provider=result.provider,
                model=result.model,
            ),
        ]

    async def act(
        self, user_id: str, message_id: int, card: int, action: int, channel: str = "web"
    ) -> list[ChatMessage]:
        """Run a card button. The action is read from the stored message, never the client."""
        msg = self.store.get_message(user_id, message_id)
        try:
            spec = msg.cards[card]["actions"][action]  # type: ignore[union-attr]
        except (AttributeError, IndexError, KeyError, TypeError):
            raise UnknownAction(f"{message_id}/{card}/{action}") from None
        kind, payload = spec["kind"], spec["payload"]
        ws = self._ws(user_id)

        if kind == "quick":
            return await self.quick(
                user_id, payload["agent"], payload["action"], payload.get("arg"), channel
            )

        thread = msg.thread
        if kind in ("approve", "send_back"):
            decision = "approved" if kind == "approve" else "sent_back"
            self.store.add_approval(
                user_id,
                Approval(
                    id=uuid.uuid4().hex[:12],
                    subject=payload["subject"],
                    decision=decision,
                    source="telegram" if channel == "telegram" else "app",
                    decided_at=datetime.now(UTC),
                ),
            )
            self._close(user_id, msg, card, "Approved" if decision == "approved" else "Sent back")
            text = (
                "Approved. It’s saved in your decision log, and I’ll keep it in mind."
                if decision == "approved"
                else "No problem, I’ve noted that you sent it back. Ask me to adjust it any time."
            )
            return [self._reply(user_id, thread, msg.author, text, [], channel, mode="action")]

        if kind == "file":
            ws.finance.bucket_overrides[payload["category"]] = payload["bucket"]
            self.store.save_workspace(user_id, ws)
            label = {"needs": "a need", "wants": "a want", "savings": "savings"}[payload["bucket"]]
            self._close(user_id, msg, card, f"Filed as {label}")
            return [
                self._reply(
                    user_id,
                    thread,
                    "penny",
                    f"Got it: {payload['category']} is now {label}. Every number has been updated.",
                    [],
                    channel,
                    mode="action",
                )
            ]

        if kind == "watch":
            if payload["symbol"] not in ws.watchlist and len(ws.watchlist) < 20:
                ws.watchlist.append(payload["symbol"])
                self.store.save_workspace(user_id, ws)
            self._close(user_id, msg, card, "On your watchlist")
            return [
                self._reply(
                    user_id,
                    thread,
                    "bruno",
                    f"Added {payload['symbol']} to your watchlist.",
                    [],
                    channel,
                    mode="action",
                )
            ]

        raise UnknownAction(kind)

    def _close(self, user_id: str, msg: ChatMessage, card: int, outcome: str) -> None:
        cards = [dict(c) for c in msg.cards]
        cards[card] = {**cards[card], "actions": [], "outcome": outcome}
        self.store.update_cards(user_id, msg.id, cards)
