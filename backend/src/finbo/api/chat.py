"""Chat with the crew, and Telegram account linking."""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from ..chat import ChatService, NotSetUp, UnknownAction
from ..crew import CREW
from ..llm import configured_providers
from .deps import CurrentUser, MarketData, StoreDep

router = APIRouter(prefix="/api")

Thread = Annotated[str, Path(pattern="^(finbo|penny|hazel|snowy|bruno|scout)$")]
LINK_CODE_MINUTES = 10


class Send(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class Quick(BaseModel):
    action: str = Field(min_length=1, max_length=40)
    arg: str | None = Field(default=None, max_length=60)


class Act(BaseModel):
    message_id: int
    card: int = Field(ge=0, le=20)
    action: int = Field(ge=0, le=20)


def _service(store, market_data) -> ChatService:
    # configured_providers is looked up at call time so tests can swap it.
    return ChatService(
        store, market_data=lambda: market_data, providers=lambda: configured_providers()
    )


def _out(messages) -> list[dict[str, Any]]:
    return [m.model_dump(mode="json") for m in messages]


@router.get("/crew")
def crew() -> list[dict[str, Any]]:
    return [m.as_dict() for m in CREW.values()]


@router.get("/me/chats")
def latest(user: CurrentUser, store: StoreDep) -> dict[str, Any]:
    """The last message of each crew thread, for conversation previews."""
    out = {}
    for crew_id in CREW:
        last = store.list_messages(user.id, crew_id, limit=1)
        if last:
            out[crew_id] = last[0].model_dump(mode="json")
    return out


@router.get("/me/chat/{thread}")
def history(thread: Thread, user: CurrentUser, store: StoreDep, market_data: MarketData):
    return _out(_service(store, market_data).history(user.id, thread))


@router.post("/me/chat/{thread}")
async def send(
    thread: Thread, body: Send, user: CurrentUser, store: StoreDep, market_data: MarketData
):
    try:
        return _out(await _service(store, market_data).send(user.id, thread, body.text))
    except NotSetUp:
        raise HTTPException(404, "not_set_up") from None


@router.post("/me/chat/{thread}/quick")
async def quick(
    thread: Thread, body: Quick, user: CurrentUser, store: StoreDep, market_data: MarketData
):
    try:
        return _out(
            await _service(store, market_data).quick(user.id, thread, body.action, body.arg)
        )
    except NotSetUp:
        raise HTTPException(404, "not_set_up") from None
    except UnknownAction:
        raise HTTPException(422, "That quick action doesn’t exist.") from None


@router.post("/me/chat-action")
async def act(body: Act, user: CurrentUser, store: StoreDep, market_data: MarketData):
    try:
        return _out(
            await _service(store, market_data).act(user.id, body.message_id, body.card, body.action)
        )
    except NotSetUp:
        raise HTTPException(404, "not_set_up") from None
    except UnknownAction:
        raise HTTPException(422, "That button is no longer available.") from None


@router.delete("/me/chat/{thread}", status_code=204)
def clear(thread: Thread, user: CurrentUser, store: StoreDep) -> None:
    store.clear_thread(user.id, thread)


def _bot() -> dict[str, Any]:
    username = os.getenv("TELEGRAM_BOT_USERNAME", "").lstrip("@")
    return {
        "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and username),
        "username": username or None,
        "url": f"https://t.me/{username}" if username else None,
    }


@router.get("/me/telegram")
def telegram_status(user: CurrentUser, store: StoreDep) -> dict[str, Any]:
    return {"linked": store.telegram_linked(user.id), "bot": _bot()}


@router.post("/me/telegram/code")
def telegram_code(user: CurrentUser, store: StoreDep) -> dict[str, Any]:
    # 8 characters from an unambiguous alphabet, valid for 10 minutes, single use.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    expires = datetime.now(UTC) + timedelta(minutes=LINK_CODE_MINUTES)
    store.create_link_code(user.id, code, expires)
    bot = _bot()
    return {
        "code": code,
        "expires_at": expires.isoformat(),
        "bot": bot,
        "deep_link": f"{bot['url']}?start=link-{code}" if bot["url"] else None,
    }
