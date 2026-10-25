"""The signed-in user's workspace: data, edits, questions and decisions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..copilot import ask_copilot
from ..core import CsvSchemaError, Debt, parse_transactions_csv
from ..llm import AllProvidersFailedError, NoProviderConfiguredError, configured_providers
from ..session import FinanceSession, Market
from ..store import Approval, Workspace
from .deps import CurrentUser, MarketData, StoreDep, require_workspace
from .views import workspace_view

router = APIRouter(prefix="/api/me")

MAX_UPLOAD_BYTES = 1_000_000
Extra = Annotated[float, Query(ge=0, le=1e9)]
Contribution = Annotated[float | None, Query(ge=0, le=1e9)]


class Setup(BaseModel):
    market: Market


class ProfileUpdate(BaseModel):
    monthly_income: Decimal = Field(ge=0, le=Decimal("1e9"))
    income_stability: Literal["stable", "variable"]
    dependents: int = Field(ge=0, le=20)
    emergency_fund_balance: Decimal = Field(ge=0, le=Decimal("1e10"))


class DebtInput(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    balance: Decimal = Field(ge=0, le=Decimal("1e10"))
    annual_rate_pct: Decimal = Field(ge=0, le=100)
    minimum_payment: Decimal = Field(gt=0, le=Decimal("1e9"))


class Classify(BaseModel):
    category: str = Field(min_length=1)
    bucket: Literal["needs", "wants", "savings"]


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class Decide(BaseModel):
    subject: str = Field(min_length=1, max_length=2000)
    decision: Literal["approved", "sent_back"]
    note: str = Field(default="", max_length=1000)


@router.get("")
def get_me(
    user: CurrentUser,
    store: StoreDep,
    extra_debt_payment: Extra = 0.0,
    ef_contribution: Contribution = None,
) -> dict[str, Any]:
    ws = require_workspace(store, user)
    return workspace_view(store, user.id, ws, extra_debt_payment, ef_contribution)


@router.post("/setup")
def setup(user: CurrentUser, store: StoreDep, body: Setup) -> dict[str, Any]:
    """Start (or restart) the workspace from a country's sample data."""
    store.delete_user(user.id)
    ws = Workspace(market=body.market, finance=FinanceSession.sample(body.market))
    store.save_workspace(user.id, ws)
    country = "India" if body.market == "in" else "the United States"
    store.add_event(user.id, "setup", f"Started on sample data for {country}", {})
    return workspace_view(store, user.id, ws)


@router.delete("", status_code=204)
def delete_me(user: CurrentUser, store: StoreDep) -> None:
    store.delete_user(user.id)


@router.put("/profile")
def update_profile(user: CurrentUser, store: StoreDep, body: ProfileUpdate) -> dict[str, Any]:
    ws = require_workspace(store, user)
    ws.finance.profile = ws.finance.profile.model_copy(update=body.model_dump())
    ws.profile_source = "edited"
    store.save_workspace(user.id, ws)
    return workspace_view(store, user.id, ws)


@router.put("/debts")
def update_debts(user: CurrentUser, store: StoreDep, body: list[DebtInput]) -> dict[str, Any]:
    if len(body) > 20:
        raise HTTPException(422, "Track up to 20 debts.")
    ws = require_workspace(store, user)
    currency = ws.finance.profile.currency
    debts = [Debt(currency=currency, **d.model_dump()) for d in body]
    ws.finance.profile = ws.finance.profile.model_copy(update={"debts": debts})
    ws.profile_source = "edited"
    store.save_workspace(user.id, ws)
    return workspace_view(store, user.id, ws)


@router.post("/classify")
def classify(user: CurrentUser, store: StoreDep, body: Classify) -> dict[str, Any]:
    ws = require_workspace(store, user)
    ws.finance.bucket_overrides[body.category] = body.bucket
    store.save_workspace(user.id, ws)
    return workspace_view(store, user.id, ws)


@router.post("/transactions", response_model=None)
async def upload_transactions(
    user: CurrentUser, store: StoreDep, file: Annotated[UploadFile, File()]
) -> dict[str, Any] | JSONResponse:
    ws = require_workspace(store, user)
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 1 MB. Upload one statement period at a time.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "File is not UTF-8 text. Export the statement as CSV.") from None
    try:
        result = parse_transactions_csv(text, ws.finance.profile.currency)
    except CsvSchemaError as e:
        return JSONResponse(status_code=422, content={"detail": str(e), "errors": []})
    if result.errors or not result.transactions:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Some rows need fixing before this statement can be used."
                if result.errors
                else "The file has no transactions.",
                "errors": [e.model_dump() for e in result.errors],
            },
        )
    ws.finance.transactions = result.transactions
    ws.finance.bucket_overrides.clear()
    ws.transactions_source = "uploaded"
    store.save_workspace(user.id, ws)
    store.add_event(
        user.id,
        "upload",
        f"Uploaded {len(result.transactions)} transactions",
        {"file": file.filename},
    )
    return workspace_view(store, user.id, ws)


@router.post("/ask")
async def ask(
    user: CurrentUser, store: StoreDep, market_data: MarketData, body: Ask
) -> dict[str, Any]:
    ws = require_workspace(store, user)
    try:
        providers = configured_providers()
    except NoProviderConfiguredError as e:
        raise HTTPException(503, str(e)) from None
    try:
        result = await ask_copilot(body.question, ws.finance, providers, market_data)
    except AllProvidersFailedError as e:
        raise HTTPException(502, str(e)) from None

    trace = [
        {"name": c.name, "arguments": c.arguments, "depth": c.depth, "ok": c.ok}
        for c in result.trace
    ]
    checks = result.checks.as_dict()
    # The audit log stores the redacted question, never the original text.
    store.add_event(
        user.id,
        "refused" if result.checks.refused else "ask",
        result.question_sent or "[question not sent to the AI]",
        {
            "answer": result.answer,
            "provider": result.provider,
            "model": result.model,
            "trace": trace,
            "checks": checks,
        },
    )
    return {
        "answer": result.answer,
        "provider": result.provider,
        "model": result.model,
        "fallbacks": result.fallbacks,
        "trace": trace,
        "checks": checks,
    }


@router.post("/approvals")
def decide(user: CurrentUser, store: StoreDep, body: Decide) -> dict[str, Any]:
    require_workspace(store, user)
    approval = Approval(id=uuid.uuid4().hex[:12], decided_at=datetime.now(UTC), **body.model_dump())
    store.add_approval(user.id, approval)
    return approval.model_dump(mode="json")


@router.get("/activity")
def activity(user: CurrentUser, store: StoreDep, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return [e.model_dump(mode="json") for e in store.list_events(user.id, limit)]
