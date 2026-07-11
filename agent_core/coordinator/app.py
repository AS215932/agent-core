"""FastAPI service for authoritative LHP-v2 coordination state."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from agent_core import __version__
from agent_core.contracts.coordination import (
    ApprovalRecord,
    CaseProjection,
    HandoffEnvelope,
    HandoffRecord,
    HandoffResult,
    LoopHeartbeat,
    LoopRegistration,
    VerificationResult,
)
from agent_core.coordination.auth import build_signature
from agent_core.coordinator.db import (
    CoordinatorStore,
    init_models,
    make_engine,
    make_sessionmaker,
)

MAX_BODY_BYTES = 65_536
MAX_CLOCK_SKEW_SECONDS = 300


DEFAULT_REGISTRATIONS = [
    LoopRegistration(
        loop_id="soc",
        display_name="SOC Agent",
        capabilities=[
            "security.triage",
            "security.attack_path",
            "security.verify",
            "soc.active_probe.rt2",
        ],
        service_name="soc-agent.service",
        host="soc",
    ),
    LoopRegistration(
        loop_id="noc",
        display_name="NOC Agent",
        capabilities=[
            "noc.network_snapshot.read",
            "noc.network_change.prepare",
            "noc.verify",
        ],
        service_name="noc-agent.service",
        host="noc",
    ),
    LoopRegistration(
        loop_id="engineering",
        display_name="Engineering Loop",
        capabilities=["engineering.repository.analyze", "engineering.draft_pr"],
        service_name="hyrule-engineering-loop.timer",
        host="loop",
    ),
    LoopRegistration(
        loop_id="knowledge",
        display_name="Knowledge Loop",
        capabilities=[
            "knowledge.context.resolve",
            "knowledge.gap.analyze",
            "knowledge.learning.proposal",
        ],
        service_name="hyrule-knowledge-loop.timer",
        host="loop",
    ),
]


def _load_keys() -> dict[str, dict[str, str]]:
    raw = os.environ.get("HYRULE_COORDINATOR_LOOP_KEYS_JSON", "").strip()
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("HYRULE_COORDINATOR_LOOP_KEYS_JSON must be valid JSON") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError("HYRULE_COORDINATOR_LOOP_KEYS_JSON must be an object")
    keys: dict[str, dict[str, str]] = {}
    for identity, value in loaded.items():
        if isinstance(value, str):
            keys[str(identity)] = {"default": value}
        elif isinstance(value, dict):
            keys[str(identity)] = {str(k): str(v) for k, v in value.items() if v}
    return keys


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class CoordinatorAuthenticator:
    keys: dict[str, dict[str, str]]
    allow_insecure_dev: bool = False

    async def authenticate(self, request: Request, store: CoordinatorStore) -> str:
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="coordinator payload exceeds 64 KiB")
        identity = request.headers.get("x-agent-loop-identity", "").strip().lower()
        if not identity:
            raise HTTPException(status_code=401, detail="missing loop identity")
        if self.allow_insecure_dev:
            return identity
        key_id = request.headers.get("x-agent-loop-key-id", "").strip()
        timestamp = request.headers.get("x-agent-loop-timestamp", "").strip()
        nonce = request.headers.get("x-agent-loop-nonce", "").strip()
        signature = request.headers.get("x-agent-loop-signature", "").strip()
        secret = self.keys.get(identity, {}).get(key_id, "")
        if not secret or not timestamp or not nonce or not signature:
            raise HTTPException(
                status_code=401, detail="missing or unknown loop signing credentials"
            )
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="invalid loop timestamp") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if abs((now - parsed.astimezone(UTC)).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
            raise HTTPException(status_code=401, detail="stale loop timestamp")
        expected = build_signature(
            secret=secret,
            method=request.method,
            path=request.url.path,
            timestamp=timestamp,
            nonce=nonce,
            key_id=key_id,
            body=body,
        )
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="invalid loop signature")
        if not await store.register_nonce(identity, nonce, now):
            raise HTTPException(status_code=409, detail="replayed loop nonce")
        return identity


class LeaseRequest(BaseModel):
    lease_seconds: int = Field(default=120, ge=30, le=900)


class ProgressRequest(BaseModel):
    summary: str = Field(default="", max_length=1000)


class CancelRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)


async def _deliver_outbox(app: FastAPI) -> None:
    collector_url = str(app.state.collector_url or "").strip()
    if not collector_url:
        return
    store: CoordinatorStore = app.state.store
    while True:
        for row_id, payload in await store.outbox_batch():
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(collector_url, json=payload)
                    response.raise_for_status()
                await store.mark_outbox(row_id)
            except Exception as exc:
                await store.mark_outbox(row_id, error=type(exc).__name__)
        await asyncio.sleep(2)


def create_app(
    *,
    database_url: str | None = None,
    keys: dict[str, dict[str, str]] | None = None,
    allow_insecure_dev: bool | None = None,
    registrations: list[LoopRegistration] | None = None,
) -> FastAPI:
    engine = make_engine(database_url)
    store = CoordinatorStore(make_sessionmaker(engine))
    authenticator = CoordinatorAuthenticator(
        keys=keys if keys is not None else _load_keys(),
        allow_insecure_dev=(
            allow_insecure_dev
            if allow_insecure_dev is not None
            else _truthy_env("HYRULE_COORDINATOR_ALLOW_INSECURE_DEV")
        ),
    )
    approved_registrations = registrations or DEFAULT_REGISTRATIONS
    capability_map = {item.loop_id: frozenset(item.capabilities) for item in approved_registrations}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await init_models(engine)
        await store.seed_loops(approved_registrations)
        outbox_task = asyncio.create_task(_deliver_outbox(app))
        try:
            yield
        finally:
            outbox_task.cancel()
            try:
                await outbox_task
            except asyncio.CancelledError:
                pass
            await engine.dispose()

    app = FastAPI(title="AS215932 Agent Coordinator", version=__version__, lifespan=lifespan)
    app.state.store = store
    app.state.engine = engine
    app.state.authenticator = authenticator
    app.state.collector_url = os.environ.get("HYRULE_COORDINATOR_COLLECTOR_URL", "")

    async def identity(request: Request) -> str:
        return await authenticator.authenticate(request, store)

    def require_observatory(actor: str) -> None:
        if actor != "observatory":
            raise HTTPException(status_code=403, detail="Observatory identity required")

    def require_visible(record: HandoffRecord, actor: str) -> None:
        if actor not in {
            "observatory",
            record.envelope.source_loop,
            record.envelope.target_loop,
        }:
            raise HTTPException(status_code=403, detail="handoff is not visible to this identity")

    async def record_or_404(handoff_id: str) -> HandoffRecord:
        record = await store.handoff(handoff_id)
        if record is None:
            raise HTTPException(status_code=404, detail="handoff not found")
        return record

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"status": "ok", "service": "agent-core-coordinator", "version": __version__}

    @app.get("/v1/loops")
    async def loops(actor: str = Depends(identity)) -> dict[str, Any]:
        del actor
        return {"loops": await store.loops()}

    @app.post("/v1/loops/{loop_id}/heartbeat")
    async def heartbeat(
        loop_id: str, payload: LoopHeartbeat, actor: str = Depends(identity)
    ) -> dict[str, Any]:
        if actor != loop_id or payload.loop_id != loop_id:
            raise HTTPException(status_code=403, detail="loop may heartbeat only itself")
        try:
            return await store.heartbeat(payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/v1/cases/{case_id}", response_model=CaseProjection)
    async def put_case(
        case_id: str, payload: CaseProjection, actor: str = Depends(identity)
    ) -> CaseProjection:
        if payload.case_id != case_id or payload.owner_loop != actor:
            raise HTTPException(status_code=403, detail="case projection owner mismatch")
        try:
            return await store.put_case(payload)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/cases")
    async def cases(
        owner_loop: str | None = None,
        status: str | None = None,
        limit: int = 100,
        actor: str = Depends(identity),
    ) -> dict[str, Any]:
        del actor
        items = await store.cases(owner_loop=owner_loop, status=status, limit=limit)
        return {"cases": [item.model_dump(mode="json") for item in items]}

    @app.get("/v1/cases/{case_id}", response_model=CaseProjection)
    async def case(case_id: str, actor: str = Depends(identity)) -> CaseProjection:
        del actor
        item = await store.case(case_id)
        if item is None:
            raise HTTPException(status_code=404, detail="case not found")
        return item

    @app.post("/v1/handoffs", response_model=HandoffRecord)
    async def create_handoff(
        payload: HandoffEnvelope, actor: str = Depends(identity)
    ) -> HandoffRecord:
        if payload.source_loop != actor:
            raise HTTPException(status_code=403, detail="source_loop must match signed identity")
        supported = capability_map.get(payload.target_loop)
        if supported is None or payload.capability not in supported:
            raise HTTPException(status_code=422, detail="target loop does not advertise capability")
        if payload.expires_at and payload.expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=422, detail="handoff is already expired")
        try:
            return await store.create_handoff(payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/handoffs")
    async def handoffs(
        source_loop: str | None = None,
        target_loop: str | None = None,
        status: str | None = None,
        case_id: str | None = None,
        limit: int = 100,
        actor: str = Depends(identity),
    ) -> dict[str, Any]:
        if actor != "observatory":
            if source_loop and source_loop != actor:
                raise HTTPException(status_code=403, detail="source filter exceeds identity scope")
            if target_loop and target_loop != actor:
                raise HTTPException(status_code=403, detail="target filter exceeds identity scope")
            if not source_loop and not target_loop:
                raise HTTPException(
                    status_code=422, detail="loop must select its source or target scope"
                )
        items = await store.handoffs(
            source_loop=source_loop,
            target_loop=target_loop,
            status=status,
            case_id=case_id,
            limit=limit,
        )
        return {"handoffs": [item.model_dump(mode="json") for item in items]}

    @app.get("/v1/inbox")
    async def inbox(
        status: str | None = None, limit: int = 100, actor: str = Depends(identity)
    ) -> dict[str, Any]:
        if actor == "observatory":
            raise HTTPException(
                status_code=403, detail="Observatory uses the handoff/approval views"
            )
        items = await store.handoffs(target_loop=actor, status=status, limit=limit)
        return {"handoffs": [item.model_dump(mode="json") for item in items]}

    @app.get("/v1/handoffs/{handoff_id}", response_model=HandoffRecord)
    async def handoff(handoff_id: str, actor: str = Depends(identity)) -> HandoffRecord:
        record = await record_or_404(handoff_id)
        require_visible(record, actor)
        return record

    @app.get("/v1/handoffs/{handoff_id}/events")
    async def handoff_events(handoff_id: str, actor: str = Depends(identity)) -> dict[str, Any]:
        record = await record_or_404(handoff_id)
        require_visible(record, actor)
        events = await store.events(handoff_id)
        return {"events": [event.model_dump(mode="json") for event in events]}

    @app.post("/v1/handoffs/{handoff_id}/claim", response_model=HandoffRecord)
    async def claim(
        handoff_id: str, payload: LeaseRequest, actor: str = Depends(identity)
    ) -> HandoffRecord:
        record = await record_or_404(handoff_id)
        if record.envelope.target_loop != actor:
            raise HTTPException(status_code=403, detail="only the target loop may claim")
        try:
            return await store.claim(handoff_id, actor, payload.lease_seconds)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/handoffs/{handoff_id}/heartbeat", response_model=HandoffRecord)
    async def heartbeat_claim(
        handoff_id: str, payload: LeaseRequest, actor: str = Depends(identity)
    ) -> HandoffRecord:
        try:
            return await store.heartbeat_claim(handoff_id, actor, payload.lease_seconds)
        except (PermissionError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/handoffs/{handoff_id}/progress", response_model=HandoffRecord)
    async def progress(
        handoff_id: str, payload: ProgressRequest, actor: str = Depends(identity)
    ) -> HandoffRecord:
        try:
            return await store.progress(handoff_id, actor, payload.summary)
        except (PermissionError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/handoffs/{handoff_id}/result", response_model=HandoffRecord)
    async def result(
        handoff_id: str, payload: HandoffResult, actor: str = Depends(identity)
    ) -> HandoffRecord:
        try:
            return await store.submit_result(handoff_id, actor, payload)
        except (PermissionError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/handoffs/{handoff_id}/verify", response_model=HandoffRecord)
    async def verify(
        handoff_id: str, payload: VerificationResult, actor: str = Depends(identity)
    ) -> HandoffRecord:
        try:
            return await store.verify(handoff_id, actor, payload)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/v1/approvals")
    async def approvals(
        status: str = "awaiting_approval",
        limit: int = 100,
        actor: str = Depends(identity),
    ) -> dict[str, Any]:
        require_observatory(actor)
        items = await store.handoffs(status=status, limit=limit)
        return {"handoffs": [item.model_dump(mode="json") for item in items]}

    @app.post("/v1/approvals/{handoff_id}/decision", response_model=HandoffRecord)
    async def approval_decision(
        handoff_id: str, payload: ApprovalRecord, actor: str = Depends(identity)
    ) -> HandoffRecord:
        require_observatory(actor)
        try:
            return await store.approve(handoff_id, payload)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/handoffs/{handoff_id}/cancel", response_model=HandoffRecord)
    async def cancel(
        handoff_id: str, payload: CancelRequest, actor: str = Depends(identity)
    ) -> HandoffRecord:
        record = await record_or_404(handoff_id)
        if actor not in {record.envelope.source_loop, "observatory"}:
            raise HTTPException(
                status_code=403, detail="only source loop or Observatory may cancel"
            )
        try:
            return await store.cancel(handoff_id, actor, payload.reason)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
