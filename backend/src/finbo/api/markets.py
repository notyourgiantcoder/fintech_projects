"""Watchlist and symbol detail. Signed-in only, to keep free data sources within limits."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import research
from ..guardrails import scan
from ..market import InvalidSymbolError, MarketDataError, history_stats, resolve_symbol
from .deps import CurrentUser, MarketData, StoreDep, require_workspace

router = APIRouter(prefix="/api")

MAX_WATCHLIST = 20


class Watchlist(BaseModel):
    symbols: list[Annotated[str, Field(min_length=1, max_length=24)]] = Field(
        max_length=MAX_WATCHLIST
    )


def _safe_titles(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in items if not scan(i["title"], use_model=False).flagged]


@router.get("/market/search")
def search(
    user: CurrentUser,
    market_data: MarketData,
    q: Annotated[str, Query(min_length=2, max_length=60)],
) -> list[dict[str, Any]]:
    try:
        return [m.model_dump() for m in market_data.search(q)]
    except MarketDataError as e:
        raise HTTPException(502, str(e)) from None


@router.get("/me/watchlist")
def get_watchlist(
    user: CurrentUser, store: StoreDep, market_data: MarketData
) -> list[dict[str, Any]]:
    ws = require_workspace(store, user)
    rows = []
    for symbol in ws.watchlist:
        try:
            rows.append(
                {"symbol": symbol, "quote": market_data.quote(symbol).model_dump(mode="json")}
            )
        except MarketDataError as e:
            rows.append({"symbol": symbol, "error": str(e)})
    return rows


@router.put("/me/watchlist")
def put_watchlist(
    user: CurrentUser, store: StoreDep, market_data: MarketData, body: Watchlist
) -> list[str]:
    ws = require_workspace(store, user)
    symbols = []
    for raw in body.symbols:
        # Already-saved symbols are trusted; new ones must resolve to a live quote.
        if raw in ws.watchlist:
            symbols.append(raw)
            continue
        try:
            symbols.append(resolve_symbol(raw, ws.market, market_data))
        except InvalidSymbolError as e:
            raise HTTPException(422, str(e)) from None
        except MarketDataError as e:
            raise HTTPException(422, str(e)) from None
    ws.watchlist = list(dict.fromkeys(symbols))  # de-duplicate, keep order
    store.save_workspace(user.id, ws)
    return ws.watchlist


@router.get("/market/symbol/{symbol}")
def symbol_detail(
    symbol: str, user: CurrentUser, store: StoreDep, market_data: MarketData
) -> dict[str, Any]:
    ws = require_workspace(store, user)
    try:
        s = resolve_symbol(symbol, ws.market, market_data)
        quote = market_data.quote(s)
    except InvalidSymbolError as e:
        raise HTTPException(422, str(e)) from None
    except MarketDataError as e:
        raise HTTPException(404, str(e)) from None

    out: dict[str, Any] = {"symbol": s, "quote": quote.model_dump(mode="json"), "errors": {}}
    try:
        out["stats"] = history_stats(s, "1y", market_data.history(s, "1y")).model_dump(mode="json")
    except (MarketDataError, ValueError) as e:
        out["errors"]["stats"] = str(e)
    try:
        out["profile"] = market_data.profile(s).model_dump(mode="json")
    except MarketDataError as e:
        out["errors"]["profile"] = str(e)

    name = (out.get("profile") or {}).get("name") or quote.name or s
    try:
        news = [i.model_dump(mode="json") for i in research.search_news(name, ws.market, 6)]
        out["news"] = _safe_titles(news)
    except research.ResearchError as e:
        out["errors"]["news"] = str(e)
    is_us = "." not in s and not s.startswith("^")
    if is_us:
        try:
            out["filings"] = [f.model_dump() for f in research.recent_filings(s, limit=4)]
        except research.ResearchError as e:
            out["errors"]["filings"] = str(e)
    return out
