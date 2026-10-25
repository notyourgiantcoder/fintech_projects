"""Shared dependencies: the store, the signed-in user's workspace, market data."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException

from ..auth import User, current_user
from ..market import MarketDataProvider, default_provider
from ..store import Store, Workspace

_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def set_store(store: Store | None) -> None:
    """Tests install an in-memory store; None makes the next call open the default."""
    global _store
    _store = store


def get_market_data() -> MarketDataProvider:
    return default_provider()


CurrentUser = Annotated[User, Depends(current_user)]
StoreDep = Annotated[Store, Depends(get_store)]
MarketData = Annotated[MarketDataProvider, Depends(get_market_data)]


def require_workspace(store: Store, user: User) -> Workspace:
    ws = store.load_workspace(user.id)
    if ws is None:
        raise HTTPException(404, "not_set_up")
    return ws
