"""Async SQLAlchemy store for collected TraceEvents.

Part of the optional ``collector`` extra (not imported by ``agent_core.contracts``).
Defaults to a local sqlite file; set ``HYRULE_COLLECTOR_DATABASE_URL`` to a Postgres
async URL (``postgresql+asyncpg://...``) in production.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./collector.db"


def database_url() -> str:
    return os.environ.get("HYRULE_COLLECTOR_DATABASE_URL", DEFAULT_DATABASE_URL)


class Base(DeclarativeBase):
    pass


class TraceEventRow(Base):
    __tablename__ = "trace_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(128), index=True, default=None)
    trace_id: Mapped[str | None] = mapped_column(String(128), index=True, default=None)
    graph_id: Mapped[str | None] = mapped_column(String(128), index=True, default=None)
    graph_version: Mapped[str | None] = mapped_column(String(128), default=None)
    node_id: Mapped[str | None] = mapped_column(String(128), default=None)
    agent_role: Mapped[str | None] = mapped_column(String(128), default=None)
    environment: Mapped[str | None] = mapped_column(String(64), default=None)
    summary: Mapped[str] = mapped_column(String, default="")
    model: Mapped[str | None] = mapped_column(String(128), default=None)
    provider: Mapped[str | None] = mapped_column(String(64), default=None)
    cost_usd: Mapped[float | None] = mapped_column(Float, default=None)
    input_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    output_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


def make_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(url or database_url(), future=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
