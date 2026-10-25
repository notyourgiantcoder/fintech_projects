"""Persistence: workspaces, approvals and the audit log.

SQLite by default (a file under data/, no setup), or Postgres (Neon's free tier) when
DATABASE_URL is set. SQLAlchemy Core keeps one code path for both.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from .core import FinancialProfile, Transaction
from .session import FinanceSession, Market

DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "finbo.db"

metadata = MetaData()

workspaces = Table(
    "workspaces",
    metadata,
    Column("user_id", String(128), primary_key=True),
    Column("market", String(2), nullable=False),
    Column("profile", JSON, nullable=False),
    Column("transactions", JSON, nullable=False),
    Column("overrides", JSON, nullable=False),
    Column("watchlist", JSON, nullable=False),
    Column("transactions_source", String(16), nullable=False),
    Column("profile_source", String(16), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

approvals = Table(
    "approvals",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("user_id", String(128), index=True, nullable=False),
    Column("subject", Text, nullable=False),
    Column("decision", String(16), nullable=False),
    Column("note", Text, nullable=False),
    Column("source", String(16), nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=False),
)

events = Table(
    "audit_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String(128), index=True, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("summary", Text, nullable=False),
    Column("payload", JSON, nullable=False),
)


chat_messages = Table(
    "chat_messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String(128), index=True, nullable=False),
    Column("thread", String(16), nullable=False),  # crew id the user is talking to
    Column("role", String(8), nullable=False),  # "user" or "agent"
    Column("author", String(16), nullable=False),  # crew id, or "you"
    Column("text", Text, nullable=False),
    Column("cards", JSON, nullable=False),
    Column("meta", JSON, nullable=False),  # contributors, checks, provider
    Column("channel", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

telegram_links = Table(
    "telegram_links",
    metadata,
    Column("telegram_id", String(32), primary_key=True),
    Column("user_id", String(128), index=True, nullable=False),
    Column("linked_at", DateTime(timezone=True), nullable=False),
)

link_codes = Table(
    "link_codes",
    metadata,
    Column("code", String(16), primary_key=True),
    Column("user_id", String(128), index=True, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)


class ChatMessage(BaseModel):
    id: int
    thread: str
    role: Literal["user", "agent"]
    author: str
    text: str
    cards: list[dict[str, Any]]
    meta: dict[str, Any]
    channel: str
    created_at: datetime


class Approval(BaseModel):
    id: str
    subject: str
    decision: Literal["approved", "sent_back"]
    note: str = ""
    source: Literal["app", "excel", "telegram"] = "app"
    decided_at: datetime


class Event(BaseModel):
    id: int
    created_at: datetime
    kind: str
    summary: str
    payload: dict[str, Any]


@dataclass
class Workspace:
    market: Market
    finance: FinanceSession
    transactions_source: Literal["sample", "uploaded"] = "sample"
    profile_source: Literal["sample", "edited"] = "sample"
    watchlist: list[str] = field(default_factory=list)


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        # Neon hands out postgres:// / postgresql:// URLs; SQLAlchemy needs the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url
    path = Path(os.getenv("FINBO_DB_PATH", DEFAULT_DB))
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def _utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; everything is stored as UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class Store:
    def __init__(self, url: str | None = None) -> None:
        url = url or database_url()
        kwargs: dict[str, Any] = {"future": True}
        if url == "sqlite://":  # in-memory, for tests: one shared connection
            kwargs |= {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
        elif url.startswith("sqlite"):
            kwargs |= {"connect_args": {"check_same_thread": False}}
        else:
            kwargs |= {"pool_pre_ping": True}
        self.engine: Engine = create_engine(url, **kwargs)
        metadata.create_all(self.engine)

    # ---------- workspaces ----------

    def load_workspace(self, user_id: str) -> Workspace | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(workspaces).where(workspaces.c.user_id == user_id)).first()
        if row is None:
            return None
        finance = FinanceSession(
            profile=FinancialProfile.model_validate(row.profile),
            transactions=[Transaction.model_validate(t) for t in row.transactions],
            bucket_overrides=dict(row.overrides),
        )
        return Workspace(
            market=row.market,
            finance=finance,
            transactions_source=row.transactions_source,
            profile_source=row.profile_source,
            watchlist=list(row.watchlist),
        )

    def save_workspace(self, user_id: str, ws: Workspace) -> None:
        values = {
            "market": ws.market,
            "profile": ws.finance.profile.model_dump(mode="json"),
            "transactions": [t.model_dump(mode="json") for t in ws.finance.transactions],
            "overrides": dict(ws.finance.bucket_overrides),
            "watchlist": list(ws.watchlist),
            "transactions_source": ws.transactions_source,
            "profile_source": ws.profile_source,
            "updated_at": datetime.now(UTC),
        }
        with self.engine.begin() as conn:
            exists = conn.execute(
                select(workspaces.c.user_id).where(workspaces.c.user_id == user_id)
            ).first()
            if exists:
                conn.execute(
                    update(workspaces).where(workspaces.c.user_id == user_id).values(**values)
                )
            else:
                conn.execute(insert(workspaces).values(user_id=user_id, **values))

    def delete_user(self, user_id: str) -> None:
        with self.engine.begin() as conn:
            for table in (workspaces, approvals, events, chat_messages, telegram_links, link_codes):
                conn.execute(delete(table).where(table.c.user_id == user_id))

    # ---------- approvals ----------

    def add_approval(self, user_id: str, approval: Approval) -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(approvals).values(user_id=user_id, **approval.model_dump()))

    def list_approvals(self, user_id: str) -> list[Approval]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(approvals)
                .where(approvals.c.user_id == user_id)
                .order_by(approvals.c.decided_at)
            ).all()
        return [
            Approval(
                id=r.id,
                subject=r.subject,
                decision=r.decision,
                note=r.note,
                source=r.source,
                decided_at=_utc(r.decided_at),
            )
            for r in rows
        ]

    # ---------- audit log ----------

    def add_event(self, user_id: str, kind: str, summary: str, payload: dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(events).values(
                    user_id=user_id,
                    created_at=datetime.now(UTC),
                    kind=kind,
                    summary=summary[:500],
                    payload=payload,
                )
            )

    def list_events(self, user_id: str, limit: int = 50) -> list[Event]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(events)
                .where(events.c.user_id == user_id)
                .order_by(events.c.id.desc())
                .limit(limit)
            ).all()
        return [
            Event(
                id=r.id,
                created_at=_utc(r.created_at),
                kind=r.kind,
                summary=r.summary,
                payload=dict(r.payload),
            )
            for r in rows
        ]

    # ---------- chat ----------

    def add_message(
        self,
        user_id: str,
        thread: str,
        role: str,
        author: str,
        text: str,
        cards: list[dict[str, Any]] | None = None,
        meta: dict[str, Any] | None = None,
        channel: str = "web",
    ) -> ChatMessage:
        now = datetime.now(UTC)
        values = {
            "user_id": user_id,
            "thread": thread,
            "role": role,
            "author": author,
            "text": text,
            "cards": cards or [],
            "meta": meta or {},
            "channel": channel,
            "created_at": now,
        }
        with self.engine.begin() as conn:
            new_id = conn.execute(insert(chat_messages).values(**values)).inserted_primary_key[0]
        return ChatMessage(id=new_id, **{k: v for k, v in values.items() if k != "user_id"})

    def list_messages(self, user_id: str, thread: str, limit: int = 50) -> list[ChatMessage]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(chat_messages)
                .where(chat_messages.c.user_id == user_id, chat_messages.c.thread == thread)
                .order_by(chat_messages.c.id.desc())
                .limit(limit)
            ).all()
        return [
            ChatMessage(
                id=r.id,
                thread=r.thread,
                role=r.role,
                author=r.author,
                text=r.text,
                cards=list(r.cards),
                meta=dict(r.meta),
                channel=r.channel,
                created_at=_utc(r.created_at),
            )
            for r in reversed(rows)
        ]

    def clear_thread(self, user_id: str, thread: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                delete(chat_messages).where(
                    chat_messages.c.user_id == user_id, chat_messages.c.thread == thread
                )
            )

    # ---------- Telegram linking ----------

    def create_link_code(self, user_id: str, code: str, expires_at: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(link_codes).where(link_codes.c.user_id == user_id))
            conn.execute(
                insert(link_codes).values(code=code, user_id=user_id, expires_at=expires_at)
            )

    def redeem_link_code(self, code: str, telegram_id: str) -> str | None:
        """Link a Telegram account to the code's owner. Returns the user id, or None."""
        now = datetime.now(UTC)
        with self.engine.begin() as conn:
            row = conn.execute(select(link_codes).where(link_codes.c.code == code)).first()
            if row is None or _utc(row.expires_at) < now:
                return None
            conn.execute(delete(link_codes).where(link_codes.c.code == code))
            conn.execute(delete(telegram_links).where(telegram_links.c.telegram_id == telegram_id))
            conn.execute(
                insert(telegram_links).values(
                    telegram_id=telegram_id, user_id=row.user_id, linked_at=now
                )
            )
            return row.user_id

    def linked_user(self, telegram_id: str) -> str | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(telegram_links.c.user_id).where(telegram_links.c.telegram_id == telegram_id)
            ).first()
        return row.user_id if row else None

    def unlink_telegram(self, telegram_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(telegram_links).where(telegram_links.c.telegram_id == telegram_id))

    def telegram_linked(self, user_id: str) -> bool:
        with self.engine.connect() as conn:
            return (
                conn.execute(
                    select(telegram_links.c.telegram_id).where(telegram_links.c.user_id == user_id)
                ).first()
                is not None
            )

    def get_message(self, user_id: str, message_id: int) -> ChatMessage | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                select(chat_messages).where(
                    chat_messages.c.id == message_id, chat_messages.c.user_id == user_id
                )
            ).first()
        if r is None:
            return None
        return ChatMessage(
            id=r.id,
            thread=r.thread,
            role=r.role,
            author=r.author,
            text=r.text,
            cards=list(r.cards),
            meta=dict(r.meta),
            channel=r.channel,
            created_at=_utc(r.created_at),
        )

    def update_cards(self, user_id: str, message_id: int, cards: list[dict[str, Any]]) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(chat_messages)
                .where(chat_messages.c.id == message_id, chat_messages.c.user_id == user_id)
                .values(cards=cards)
            )
