"""Response shapes. Every figure comes from the same tools the agents call."""

from __future__ import annotations

from typing import Any

from ..calc import calculations
from ..store import Store, Workspace

__all__ = ["calculations", "workspace_view"]


def workspace_view(
    store: Store,
    user_id: str,
    ws: Workspace,
    extra_debt_payment: float = 0.0,
    ef_contribution: float | None = None,
) -> dict[str, Any]:
    return {
        **calculations(ws.market, ws.finance, extra_debt_payment, ef_contribution),
        "sources": {"transactions": ws.transactions_source, "profile": ws.profile_source},
        "watchlist": ws.watchlist,
        "approvals": [a.model_dump(mode="json") for a in store.list_approvals(user_id)],
    }
