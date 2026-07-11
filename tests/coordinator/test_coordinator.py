from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest

from agent_core.contracts import (
    ApprovalRecord,
    CaseProjection,
    HandoffEnvelope,
    HandoffResult,
    VerificationResult,
    utcnow,
)
from agent_core.coordination import CoordinatorClient, LoopRequestSigner
from agent_core.coordinator.app import create_app

KEYS = {
    "soc": {"v1": "soc-secret-at-least-32-characters-long"},
    "knowledge": {"v1": "knowledge-secret-at-least-32-chars"},
    "engineering": {"v1": "engineering-secret-at-least-32-char"},
    "noc": {"v1": "noc-secret-at-least-32-characters-long"},
    "observatory": {"v1": "observatory-secret-at-least-32-chars"},
}


def _client(app: object, loop_id: str) -> CoordinatorClient:
    return CoordinatorClient(
        "http://coordinator",
        signer=LoopRequestSigner(loop_id, "v1", KEYS[loop_id]["v1"]),
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_full_handoff_lifecycle_and_case_projection(tmp_path) -> None:
    app = create_app(database_url=f"sqlite+aiosqlite:///{tmp_path / 'coordinator.db'}", keys=KEYS)
    async with app.router.lifespan_context(app):
        soc = _client(app, "soc")
        knowledge = _client(app, "knowledge")

        projection = await soc.put_case(
            CaseProjection(
                case_id="soc_case_1",
                owner_loop="soc",
                title="Posture drift",
                summary="Sanitized case projection",
            )
        )
        assert projection.owner_loop == "soc"
        assert (await knowledge.cases(owner_loop="soc"))[0].case_id == "soc_case_1"

        envelope = HandoffEnvelope(
            source_loop="soc",
            target_loop="knowledge",
            capability="knowledge.context.resolve",
            case_id="soc_case_1",
            summary="Resolve governed context",
            payload={"query": "expected TLS policy"},
            idempotency_key="soc_case_1:knowledge-context",
        )
        created = await soc.create_handoff(envelope)
        assert created.status == "queued"

        duplicate = await soc.create_handoff(envelope)
        assert duplicate.envelope.handoff_id == created.envelope.handoff_id

        inbox = await knowledge.inbox(status="queued")
        assert [item.envelope.handoff_id for item in inbox] == [envelope.handoff_id]
        claimed = await knowledge.claim(envelope.handoff_id)
        assert claimed.status == "claimed"
        progress = await knowledge.progress(envelope.handoff_id, "context resolved")
        assert progress.status == "in_progress"
        submitted = await knowledge.submit_result(
            HandoffResult(
                handoff_id=envelope.handoff_id,
                outcome="succeeded",
                summary="Returned cited context",
                payload={"context_pack_id": "ctx_1"},
            )
        )
        assert submitted.status == "result_submitted"
        verified = await soc.verify(
            VerificationResult(
                handoff_id=envelope.handoff_id,
                verdict="passed",
                summary="Context was consumed",
            )
        )
        assert verified.status == "completed"


@pytest.mark.asyncio
async def test_senior_approval_and_replay_protection(tmp_path) -> None:
    app = create_app(database_url=f"sqlite+aiosqlite:///{tmp_path / 'coordinator.db'}", keys=KEYS)
    async with app.router.lifespan_context(app):
        soc = _client(app, "soc")
        observatory = _client(app, "observatory")
        envelope = HandoffEnvelope(
            source_loop="soc",
            target_loop="soc",
            capability="soc.active_probe.rt2",
            approval_tier="senior",
            risk_level="high",
            payload={"probe_kind": "tls_handshake", "targets": ["web.as215932.net"]},
            idempotency_key="probe:tls:web",
        )
        created = await soc.create_handoff(envelope)
        assert created.status == "awaiting_approval"
        assert len(await observatory.approvals()) == 1

        with pytest.raises(Exception, match="senior approval"):
            await observatory.approve(
                ApprovalRecord(
                    handoff_id=envelope.handoff_id,
                    scope_hash=envelope.scope_hash,
                    decision="approved",
                    approver_id="100",
                    approver_role="operator",
                )
            )

        approved = await observatory.approve(
            ApprovalRecord(
                handoff_id=envelope.handoff_id,
                scope_hash=envelope.scope_hash,
                decision="approved",
                approver_id="101",
                approver_login="owner",
                approver_role="senior",
                expires_at=utcnow() + timedelta(minutes=15),
            )
        )
        assert approved.status == "queued"
        assert (await soc.claim(envelope.handoff_id)).status == "claimed"

        signer = LoopRequestSigner("soc", "v1", KEYS["soc"]["v1"])
        headers = signer.headers(method="GET", path="/v1/loops")
        async with httpx.AsyncClient(
            base_url="http://coordinator", transport=httpx.ASGITransport(app=app)
        ) as raw:
            assert (await raw.get("/v1/loops", headers=headers)).status_code == 200
            replay = await raw.get("/v1/loops", headers=headers)
        assert replay.status_code == 409
        assert replay.json()["detail"] == "replayed loop nonce"


@pytest.mark.asyncio
async def test_signature_covers_body(tmp_path) -> None:
    app = create_app(database_url=f"sqlite+aiosqlite:///{tmp_path / 'coordinator.db'}", keys=KEYS)
    async with app.router.lifespan_context(app):
        body = json.dumps({"loop_id": "soc", "status": "active"}).encode()
        signer = LoopRequestSigner("soc", "v1", KEYS["soc"]["v1"])
        headers = signer.headers(method="POST", path="/v1/loops/soc/heartbeat", body=body)
        tampered = json.dumps({"loop_id": "soc", "status": "degraded"}).encode()
        async with httpx.AsyncClient(
            base_url="http://coordinator", transport=httpx.ASGITransport(app=app)
        ) as raw:
            response = await raw.post(
                "/v1/loops/soc/heartbeat",
                content=tampered,
                headers={**headers, "Content-Type": "application/json"},
            )
        assert response.status_code == 401
