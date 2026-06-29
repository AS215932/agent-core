"""Minimal FastAPI trace collector.

Accepts agent-core ``TraceEvent`` payloads (validated by the shared contract) and stores
them in Postgres/sqlite. Part of the optional ``collector`` extra.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
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
from agent_core.contracts.observatory import (
    ActorRef,
    LoopRuntimeSnapshot,
    LoopTopology,
    ObservatoryLink,
    RunSummary,
    TimelineItem,
    TopologyEdge,
    TopologyNode,
)
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


_ACTION_STATUSES = {
    "pending",
    "in_progress",
    "succeeded",
    "failed",
    "blocked",
    "skipped",
    "cancelled",
    "unknown",
}
_STATUS_ALIASES = {
    "pass": "succeeded",
    "passed": "succeeded",
    "success": "succeeded",
    "successful": "succeeded",
    "ok": "succeeded",
    "error": "failed",
    "failure": "failed",
}
_SEVERITIES = {"critical", "high", "medium", "low", "info", "unknown"}


def _limit(value: int, *, default: int = 50, maximum: int = 500) -> int:
    if value <= 0:
        return default
    return min(value, maximum)


def _event(row: TraceEventRow) -> dict[str, Any]:
    return row.event if isinstance(row.event, dict) else {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _event_text(row: TraceEventRow, key: str) -> str:
    return _text(_event(row).get(key))


def _event_links(row: TraceEventRow) -> list[ObservatoryLink]:
    raw_links = _event(row).get("links", [])
    if not isinstance(raw_links, list):
        return []
    links: list[ObservatoryLink] = []
    for raw in raw_links[:20]:
        if not isinstance(raw, dict):
            continue
        try:
            links.append(ObservatoryLink.model_validate(raw))
        except Exception:
            continue
    return links


def _status_from_row(row: TraceEventRow) -> str:
    event = _event(row)
    raw_payload = event.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    raw = _text(payload.get("status") or event.get("status") or row.event_type).strip().lower()
    normalized = _STATUS_ALIASES.get(raw, raw)
    if normalized in _ACTION_STATUSES:
        return normalized
    if "fail" in raw or "error" in raw:
        return "failed"
    return "unknown"


def _severity_from_row(row: TraceEventRow) -> str:
    event = _event(row)
    raw_payload = event.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    raw = _text(payload.get("severity") or event.get("severity")).strip().lower()
    return raw if raw in _SEVERITIES else "unknown"


def _occurred_at(row: TraceEventRow) -> datetime:
    return row.timestamp or row.received_at or utcnow()


def _timeline_item_from_row(row: TraceEventRow) -> TimelineItem:
    actor = None
    if row.agent_role:
        actor = ActorRef(
            actor_id=row.agent_role,
            actor_type="loop",
            role=row.agent_role,
            loop_id=row.graph_id or "",
        )
    return TimelineItem(
        item_id=row.event_id or f"trace_row_{row.id}",
        item_type="trace_event",
        title=row.event_type,
        summary=row.summary or "",
        status=_status_from_row(row),
        severity=_severity_from_row(row),
        occurred_at=_occurred_at(row),
        source_loop=row.graph_id or _event_text(row, "graph_id"),
        source_system="agent-core-collector",
        actor=actor,
        parent_item_id=_event_text(row, "parent_event_id"),
        run_id=row.run_id or _event_text(row, "run_id"),
        trace_event_id=row.event_id,
        case_id=_event_text(row, "case_id"),
        handoff_id=_event_text(row, "handoff_id"),
        objective_id=_event_text(row, "objective_id"),
        change_id=_event_text(row, "change_id"),
        repository=_event_text(row, "repository"),
        links=_event_links(row),
        payload=_event(row),
    )


def _run_id(row: TraceEventRow) -> str:
    return row.run_id or _event_text(row, "run_id")


def _latest_time(rows: list[TraceEventRow]) -> Any:
    if not rows:
        return None
    return max(_occurred_at(row) for row in rows)


def _run_summary(run_id: str, rows: list[TraceEventRow]) -> RunSummary:
    ordered = sorted(rows, key=_occurred_at)
    graph_id = next((row.graph_id for row in ordered if row.graph_id), "")
    statuses = {_status_from_row(row) for row in ordered}
    status = "failed" if "failed" in statuses else "succeeded"
    cost_values = [row.cost_usd for row in ordered if row.cost_usd is not None]
    input_values = [row.input_tokens for row in ordered if row.input_tokens is not None]
    output_values = [row.output_tokens for row in ordered if row.output_tokens is not None]
    case_ids = sorted(
        {_event_text(row, "case_id") for row in ordered if _event_text(row, "case_id")}
    )
    handoff_ids = sorted(
        {_event_text(row, "handoff_id") for row in ordered if _event_text(row, "handoff_id")}
    )
    change_ids = sorted(
        {_event_text(row, "change_id") for row in ordered if _event_text(row, "change_id")}
    )
    return RunSummary(
        run_id=run_id,
        loop_id=graph_id,
        graph_id=graph_id,
        trace_id=next((row.trace_id for row in ordered if row.trace_id), ""),
        status=status if ordered else "unknown",
        title=f"{graph_id or 'trace'} run {run_id}",
        summary=f"{len(ordered)} trace event(s)",
        started_at=_occurred_at(ordered[0]) if ordered else None,
        ended_at=_occurred_at(ordered[-1]) if ordered else None,
        last_event_at=_latest_time(ordered),
        event_count=len(ordered),
        error_count=sum(1 for row in ordered if _status_from_row(row) == "failed"),
        cost_usd=sum(cost_values) if cost_values else None,
        input_tokens=sum(input_values) if input_values else None,
        output_tokens=sum(output_values) if output_values else None,
        case_ids=case_ids,
        handoff_ids=handoff_ids,
        change_ids=change_ids,
    )


def _action_matches(
    row: TraceEventRow,
    *,
    graph_id: str | None,
    case_id: str | None,
    handoff_id: str | None,
    change_id: str | None,
) -> bool:
    if graph_id and row.graph_id != graph_id:
        return False
    if case_id and _event_text(row, "case_id") != case_id:
        return False
    if handoff_id and _event_text(row, "handoff_id") != handoff_id:
        return False
    if change_id and _event_text(row, "change_id") != change_id:
        return False
    return True


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
        stmt = select(TraceEventRow).order_by(TraceEventRow.id.desc()).limit(_limit(limit))
        if run_id:
            stmt = stmt.where(TraceEventRow.run_id == run_id)
        async with sessionmaker() as session:
            rows = list((await session.execute(stmt)).scalars().all())
        return [row.event for row in rows]

    @app.get("/v1/loops")
    async def loops(limit: int = 2000) -> list[dict[str, Any]]:
        stmt = (
            select(TraceEventRow)
            .order_by(TraceEventRow.id.desc())
            .limit(_limit(limit, maximum=5000))
        )
        async with sessionmaker() as session:
            rows = list((await session.execute(stmt)).scalars().all())
        grouped: dict[str, list[TraceEventRow]] = {}
        for row in rows:
            loop_id = row.graph_id or _event_text(row, "graph_id") or "unknown"
            grouped.setdefault(loop_id, []).append(row)
        snapshots = []
        for loop_id, loop_rows in grouped.items():
            latest = max(loop_rows, key=_occurred_at)
            failed_count = sum(1 for row in loop_rows if _status_from_row(row) == "failed")
            pending_count = sum(
                1 for row in loop_rows if _status_from_row(row) in {"pending", "in_progress"}
            )
            snapshots.append(
                LoopRuntimeSnapshot(
                    loop_id=loop_id,
                    status="active",
                    summary=f"{len(loop_rows)} recent trace event(s)",
                    active_run_id=_run_id(latest),
                    active_case_id=_event_text(latest, "case_id"),
                    active_handoff_id=_event_text(latest, "handoff_id"),
                    recent_action_count=len(loop_rows),
                    pending_action_count=pending_count,
                    failed_action_count=failed_count,
                    last_event_at=_latest_time(loop_rows),
                )
            )
        snapshots.sort(key=lambda item: item.last_event_at or utcnow(), reverse=True)
        return [item.model_dump(mode="json") for item in snapshots]

    @app.get("/v1/runs")
    async def runs(limit: int = 50) -> list[dict[str, Any]]:
        row_limit = _limit(limit, maximum=500) * 50
        stmt = select(TraceEventRow).order_by(TraceEventRow.id.desc()).limit(min(row_limit, 5000))
        async with sessionmaker() as session:
            rows = list((await session.execute(stmt)).scalars().all())
        grouped: dict[str, list[TraceEventRow]] = {}
        for row in rows:
            run = _run_id(row)
            if run:
                grouped.setdefault(run, []).append(row)
        summaries = [_run_summary(run, run_rows) for run, run_rows in grouped.items()]
        summaries.sort(key=lambda item: item.last_event_at or utcnow(), reverse=True)
        return [item.model_dump(mode="json") for item in summaries[: _limit(limit)]]

    @app.get("/v1/runs/{run_id}")
    async def run_detail(run_id: str) -> dict[str, Any]:
        stmt = (
            select(TraceEventRow)
            .where(TraceEventRow.run_id == run_id)
            .order_by(TraceEventRow.id.asc())
        )
        async with sessionmaker() as session:
            rows = list((await session.execute(stmt)).scalars().all())
        if not rows:
            raise HTTPException(status_code=404, detail="run not found")
        return _run_summary(run_id, rows).model_dump(mode="json")

    @app.get("/v1/runs/{run_id}/events")
    async def run_events(run_id: str, limit: int = 500) -> list[dict[str, Any]]:
        stmt = (
            select(TraceEventRow)
            .where(TraceEventRow.run_id == run_id)
            .order_by(TraceEventRow.id.asc())
            .limit(_limit(limit))
        )
        async with sessionmaker() as session:
            rows = list((await session.execute(stmt)).scalars().all())
        if not rows:
            raise HTTPException(status_code=404, detail="run not found")
        return [_timeline_item_from_row(row).model_dump(mode="json") for row in rows]

    @app.get("/v1/actions")
    async def actions(
        graph_id: str | None = None,
        case_id: str | None = None,
        handoff_id: str | None = None,
        change_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        row_limit = _limit(limit, maximum=500) * 20
        stmt = select(TraceEventRow).order_by(TraceEventRow.id.desc()).limit(min(row_limit, 5000))
        if graph_id:
            stmt = stmt.where(TraceEventRow.graph_id == graph_id)
        async with sessionmaker() as session:
            rows = list((await session.execute(stmt)).scalars().all())
        filtered = [
            row
            for row in rows
            if _action_matches(
                row,
                graph_id=graph_id,
                case_id=case_id,
                handoff_id=handoff_id,
                change_id=change_id,
            )
        ]
        return [
            _timeline_item_from_row(row).model_dump(mode="json")
            for row in filtered[: _limit(limit)]
        ]

    @app.get("/v1/topology")
    async def topology(limit: int = 2000) -> dict[str, Any]:
        stmt = (
            select(TraceEventRow)
            .order_by(TraceEventRow.id.desc())
            .limit(_limit(limit, maximum=5000))
        )
        async with sessionmaker() as session:
            rows = list((await session.execute(stmt)).scalars().all())
        loop_ids = set()
        for row in rows:
            loop_id = row.graph_id or _event_text(row, "graph_id")
            if loop_id:
                loop_ids.add(loop_id)
        nodes = [
            TopologyNode(
                node_id="agent-core-collector",
                kind="collector",
                label="Agent-Core Collector",
                status="active",
            )
        ]
        edges: list[TopologyEdge] = []
        for loop_id in sorted(loop_ids):
            nodes.append(TopologyNode(node_id=loop_id, kind="loop", label=loop_id, status="active"))
            edges.append(
                TopologyEdge(
                    source_id=loop_id,
                    target_id="agent-core-collector",
                    kind="emits_trace",
                    status="succeeded",
                    label="ships TraceEvent",
                )
            )
        return LoopTopology(nodes=nodes, edges=edges).model_dump(mode="json")

    @app.get("/v1/metrics/daily")
    async def daily_metrics(limit: int = 10000) -> list[dict[str, Any]]:
        stmt = (
            select(TraceEventRow)
            .order_by(TraceEventRow.id.desc())
            .limit(_limit(limit, maximum=10000))
        )
        async with sessionmaker() as session:
            rows = list((await session.execute(stmt)).scalars().all())
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            day = row.received_at.date().isoformat()
            bucket = grouped.setdefault(
                day,
                {
                    "date": day,
                    "event_count": 0,
                    "run_ids": set(),
                    "graph_counts": {},
                    "cost_usd": 0.0,
                },
            )
            bucket["event_count"] += 1
            if _run_id(row):
                bucket["run_ids"].add(_run_id(row))
            graph = row.graph_id or _event_text(row, "graph_id") or "unknown"
            bucket["graph_counts"][graph] = bucket["graph_counts"].get(graph, 0) + 1
            bucket["cost_usd"] += row.cost_usd or 0.0
        rendered = []
        for day, bucket in sorted(grouped.items(), reverse=True):
            rendered.append(
                {
                    "date": day,
                    "event_count": bucket["event_count"],
                    "run_count": len(bucket["run_ids"]),
                    "graph_counts": bucket["graph_counts"],
                    "cost_usd": round(bucket["cost_usd"], 6),
                }
            )
        return rendered

    return app
