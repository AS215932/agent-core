"""Minimal FastAPI trace collector.

Accepts agent-core ``TraceEvent`` payloads (validated by the shared contract) and stores
them in Postgres/sqlite. Part of the optional ``collector`` extra.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastapi import FastAPI, HTTPException
from sqlalchemy import select, text

from agent_core.collector.db import (
    TraceEventRow,
    init_models,
    make_engine,
    make_sessionmaker,
)
from agent_core.contracts._base import utcnow
from agent_core.contracts.tracing import TraceEvent


def _package_version() -> str:
    try:
        return version("agent-core")
    except PackageNotFoundError:
        from agent_core import __version__

        return __version__


def _row_from_event(event: TraceEvent) -> TraceEventRow:
    cost = event.cost
    return TraceEventRow(
        event_id=event.event_id,
        event_type=event.event_type,
        run_id=event.run_id,
        trace_id=event.trace_id,
        graph_id=event.graph_id,
        graph_version=event.graph_version,
        node_id=event.node_id,
        agent_role=event.agent_role,
        environment=event.environment,
        summary=event.summary,
        model=cost.model if cost else None,
        provider=cost.provider if cost else None,
        cost_usd=cost.usd if cost else None,
        input_tokens=cost.input_tokens if cost else None,
        output_tokens=cost.output_tokens if cost else None,
        timestamp=event.timestamp,
        received_at=utcnow(),
        event=event.model_dump(mode="json"),
    )


def create_app(database_url: str | None = None) -> FastAPI:
    engine = make_engine(database_url)
    sessionmaker = make_sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await init_models(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="agent-core trace collector", version=_package_version(), lifespan=lifespan)
    app.state.collector_sessionmaker = sessionmaker

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        try:
            async with app.state.collector_sessionmaker() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        return {"status": "ok"}

    @app.post("/v1/trace")
    async def ingest(event: TraceEvent) -> dict[str, str]:
        async with sessionmaker() as session:
            session.add(_row_from_event(event))
            await session.commit()
        return {"status": "stored", "event_id": event.event_id}

    @app.post("/v1/trace/batch")
    async def ingest_batch(events: list[TraceEvent]) -> dict[str, int]:
        async with sessionmaker() as session:
            session.add_all([_row_from_event(event) for event in events])
            await session.commit()
        return {"stored": len(events)}

    @app.get("/v1/trace")
    async def recent(run_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        stmt = select(TraceEventRow).order_by(TraceEventRow.id.desc()).limit(min(limit, 500))
        if run_id:
            stmt = stmt.where(TraceEventRow.run_id == run_id)
        async with sessionmaker() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [row.event for row in rows]

    return app
