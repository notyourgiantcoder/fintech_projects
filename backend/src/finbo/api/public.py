from __future__ import annotations

import contextlib
import os
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from ..auth import auth_mode
from ..chat import QUICK, Ctx
from ..llm import PROVIDERS, NoProviderConfiguredError, configured_providers
from ..market import default_provider
from ..session import FinanceSession, Market
from ..store import Store, Workspace
from .views import calculations

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, Any]:
    names = set()
    with contextlib.suppress(NoProviderConfiguredError):
        names = {cp.provider.name for cp in configured_providers()}
    username = os.getenv("TELEGRAM_BOT_USERNAME", "").lstrip("@")
    return {
        "auth": auth_mode(),
        "providers": [{"name": p.name, "configured": p.name in names} for p in PROVIDERS],
        "microsoft": bool(os.getenv("MS_CLIENT_ID")),
        "telegram": {
            "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and username),
            "url": f"https://t.me/{username}" if username else None,
        },
    }


@router.get("/demo")
def demo(
    market: Market = "in", extra_debt_payment: Annotated[float, Query(ge=0, le=1e9)] = 0.0
) -> dict[str, Any]:
    """Sample-data calculations for the public landing page. No account, nothing stored."""
    return calculations(market, FinanceSession.sample(market), extra_debt_payment)


DEMO_ACTIONS = {
    ("snowy", "debt_free"),
    ("snowy", "compare"),
    ("hazel", "safety_net"),
    ("penny", "spending"),
    ("finbo", "glance"),
}


@router.get("/demo/quick/{agent}/{action}")
def demo_quick(agent: str, action: str, market: Market = "in", arg: str | None = None):
    """A real crew reply computed on sample data, for the landing page. Nothing is stored."""
    if (agent, action) not in DEMO_ACTIONS:
        raise HTTPException(404, "Not a demo question")
    store = Store("sqlite://")
    store.save_workspace("demo", Workspace(market=market, finance=FinanceSession.sample(market)))
    text, cards = QUICK[(agent, action)](
        Ctx(store.load_workspace("demo"), store, "demo", default_provider(), arg)
    )
    for card in cards:
        card["actions"] = []  # buttons need an account
    return {"author": agent, "text": text, "cards": cards}
