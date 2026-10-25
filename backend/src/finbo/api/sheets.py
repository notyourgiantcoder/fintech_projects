"""Excel export/import and OneDrive/SharePoint sync."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import Response

from .. import graph
from ..excel import WorkbookError, build_workbook, proposals, read_decisions
from ..store import Approval, Store
from .deps import CurrentUser, StoreDep, require_workspace
from .views import calculations

router = APIRouter(prefix="/api/me")

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_BYTES = 2_000_000
GraphToken = Annotated[str, Header(alias="X-Graph-Token", min_length=20)]


def _workbook(store: Store, user_id: str) -> bytes:
    ws = store.load_workspace(user_id)
    calc = calculations(ws.market, ws.finance)
    return build_workbook(ws, calc, store.list_approvals(user_id))


def _apply_decisions(store: Store, user_id: str, data: bytes, source: str) -> dict[str, Any]:
    ws = store.load_workspace(user_id)
    if ws is None:
        raise HTTPException(404, "not_set_up")
    current = proposals(calculations(ws.market, ws.finance))
    try:
        rows = read_decisions(data, current)
    except WorkbookError as e:
        raise HTTPException(422, str(e)) from None
    already = {a.subject for a in store.list_approvals(user_id)}
    recorded = []
    for proposal, decision, note in rows:
        if proposal.subject in already:
            continue
        approval = Approval(
            id=uuid.uuid4().hex[:12],
            subject=proposal.subject,
            decision=decision,
            note=note,
            source="excel",
            decided_at=datetime.now(UTC),
        )
        store.add_approval(user_id, approval)
        recorded.append(approval.model_dump(mode="json"))
    count = f"{len(recorded)} decision{'' if len(recorded) == 1 else 's'}"
    store.add_event(user_id, "excel_import", f"Imported {count} from {source}", {})
    return {"recorded": recorded}


@router.get("/export.xlsx")
def export_xlsx(user: CurrentUser, store: StoreDep) -> Response:
    require_workspace(store, user)
    filename = f"finbo-plan-{date.today().isoformat()}.xlsx"
    return Response(
        _workbook(store, user.id),
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import.xlsx")
async def import_xlsx(user: CurrentUser, store: StoreDep, file: Annotated[UploadFile, File()]):
    require_workspace(store, user)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "The workbook is larger than 2 MB.")
    return _apply_decisions(store, user.id, data, file.filename or "an uploaded workbook")


@router.post("/onedrive/push")
def onedrive_push(user: CurrentUser, store: StoreDep, token: GraphToken) -> dict[str, Any]:
    require_workspace(store, user)
    try:
        url = graph.upload(token, _workbook(store, user.id))
    except graph.GraphError as e:
        raise HTTPException(e.status if e.status < 500 else 502, str(e)) from None
    store.add_event(user.id, "onedrive_push", "Saved the plan workbook to OneDrive", {"url": url})
    return {"web_url": url, "path": graph.DEFAULT_PATH}


@router.post("/onedrive/pull")
def onedrive_pull(user: CurrentUser, store: StoreDep, token: GraphToken) -> dict[str, Any]:
    require_workspace(store, user)
    try:
        data = graph.download(token)
    except graph.GraphError as e:
        raise HTTPException(e.status if e.status < 500 else 502, str(e)) from None
    return _apply_decisions(store, user.id, data, "OneDrive")
