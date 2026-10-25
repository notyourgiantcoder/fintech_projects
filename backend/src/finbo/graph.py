"""Microsoft Graph file sync: push and pull the plan workbook.

The same driveItem API serves personal OneDrive, OneDrive for Business and SharePoint
document libraries; MS_GRAPH_DRIVE selects which (default "me/drive", or for a
SharePoint library "sites/{site-id}/drive").

The browser obtains a delegated Graph token through MSAL (Files.ReadWrite) and sends it
per request. The server never stores it.
"""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx

GRAPH = "https://graph.microsoft.com/v1.0"
DEFAULT_PATH = "Finbo/Finbo plan.xlsx"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class GraphError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _drive() -> str:
    return os.getenv("MS_GRAPH_DRIVE", "me/drive").strip("/")


def _item_url(path: str) -> str:
    return f"{GRAPH}/{_drive()}/root:/{quote(path)}:/content"


def _raise(res: httpx.Response) -> None:
    if res.status_code in (401, 403):
        raise GraphError(
            res.status_code, "Microsoft rejected the sign-in. Connect your account again."
        )
    if res.status_code == 404:
        raise GraphError(404, "No Finbo workbook in your OneDrive yet. Push one first.")
    if res.status_code >= 400:
        raise GraphError(res.status_code, f"Microsoft Graph returned HTTP {res.status_code}.")


def upload(
    token: str, content: bytes, path: str = DEFAULT_PATH, http: httpx.Client | None = None
) -> str:
    """Upload (or overwrite) the workbook. Returns its web URL."""
    own = http is None
    http = http or httpx.Client(timeout=20.0)
    try:
        res = http.put(
            _item_url(path),
            content=content,
            headers={"Authorization": f"Bearer {token}", "Content-Type": XLSX},
        )
        _raise(res)
        return res.json().get("webUrl", "")
    except httpx.HTTPError as e:
        raise GraphError(502, f"Couldn’t reach Microsoft Graph ({type(e).__name__}).") from e
    finally:
        if own:
            http.close()


def download(token: str, path: str = DEFAULT_PATH, http: httpx.Client | None = None) -> bytes:
    own = http is None
    http = http or httpx.Client(timeout=20.0)
    try:
        res = http.get(
            _item_url(path),
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=True,
        )
        _raise(res)
        if len(res.content) > 5_000_000:
            raise GraphError(413, "The workbook is larger than 5 MB.")
        return res.content
    except httpx.HTTPError as e:
        raise GraphError(502, f"Couldn’t reach Microsoft Graph ({type(e).__name__}).") from e
    finally:
        if own:
            http.close()
