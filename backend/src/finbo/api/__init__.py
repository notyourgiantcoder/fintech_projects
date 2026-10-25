"""HTTP API for the web app.

Each signed-in user (Clerk JWT, see auth.py) has a workspace in the store (SQLite by
default, Postgres when DATABASE_URL is set). When FINBO_STATIC_DIR points at the
built frontend, the same process serves it, so one container is a complete deployment.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ..llm import load_env
from ..observability import configure_tracing
from . import chat, markets, me, public, sheets
from .deps import get_store

load_env()
configure_tracing()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Optionally run the Telegram bot inside the API process (one free container for both).

    Set FINBO_TELEGRAM_IN_API=1 with TELEGRAM_BOT_TOKEN. Otherwise run `finbo telegram`.
    """
    bot = None
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token and os.getenv("FINBO_TELEGRAM_IN_API") == "1":
        from ..chat import ChatService
        from ..telegram_bot import build_application

        store = get_store()
        bot = build_application(token, store, ChatService(store))
        await bot.initialize()
        await bot.start()
        await bot.updater.start_polling()
    try:
        yield
    finally:
        if bot is not None:
            await bot.updater.stop()
            await bot.stop()
            await bot.shutdown()


app = FastAPI(title="Finbo API", version="0.5.0", lifespan=lifespan)
for module in (public, me, markets, sheets, chat):
    app.include_router(module.router)


def _mount_frontend(static_dir: Path) -> None:
    index = static_dir / "index.html"
    root = static_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (static_dir / path).resolve()
        # Serve real files from the build; everything else gets the SPA shell.
        if path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


_static = os.getenv("FINBO_STATIC_DIR")
if _static and (Path(_static) / "index.html").is_file():
    _mount_frontend(Path(_static))
