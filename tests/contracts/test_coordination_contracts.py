from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from agent_core.contracts import (
    ApprovalRecord,
    HandoffEnvelope,
    ProbePlan,
    SourceRef,
    utcnow,
)


def test_handoff_scope_hash_is_stable_and_detects_mutation() -> None:
    envelope = HandoffEnvelope(
        source_loop="soc",
        target_loop="engineering",
        capability="engineering.draft_pr",
        summary="Draft a bounded configuration change",
        risk_level="medium",
        approval_tier="operator",
        payload={"repository": "AS215932/network-operations", "paths": ["docs/"]},
        idempotency_key="soc:case-1:engineering",
    )
    assert len(envelope.scope_hash) == 64

    dumped = envelope.model_dump(mode="json")
    assert HandoffEnvelope.model_validate(dumped).scope_hash == envelope.scope_hash
    dumped["payload"]["paths"] = ["ansible/"]
    with pytest.raises(ValidationError, match="scope_hash"):
        HandoffEnvelope.model_validate(dumped)


def test_probe_plan_enforces_rt2_bounds() -> None:
    plan = ProbePlan(
        probe_kind="tcp_connect_sweep",
        targets=["web.as215932.net"],
        ports=[80, 443],
        approved_asset_refs=[SourceRef(ref="okf:asset:web", authority="A1")],
    )
    assert plan.max_concurrency == 2
    assert plan.max_requests == 100

    with pytest.raises(ValidationError):
        ProbePlan(
            probe_kind="tcp_connect_sweep",
            targets=["one", "two", "three", "four"],
            ports=[443],
            approved_asset_refs=[SourceRef(ref="okf:asset:web", authority="A1")],
        )


def test_approval_is_bound_to_scope_and_can_expire() -> None:
    envelope = HandoffEnvelope(
        source_loop="soc",
        target_loop="soc",
        capability="soc.active_probe.rt2",
        approval_tier="senior",
        payload={"probe_kind": "tls_handshake"},
        idempotency_key="probe:one",
    )
    approval = ApprovalRecord(
        handoff_id=envelope.handoff_id,
        scope_hash=envelope.scope_hash,
        decision="approved",
        approver_id="123",
        approver_login="operator",
        approver_role="senior",
        expires_at=utcnow() + timedelta(minutes=15),
    )
    assert approval.scope_hash == envelope.scope_hash
