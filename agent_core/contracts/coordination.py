"""Loop Handoff Protocol v2 coordination contracts.

The contracts in this module are transport-neutral.  They define the bounded,
sanitized objects exchanged through the coordinator without turning
``agent-core`` into an agent runtime.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from agent_core.contracts._base import RiskLevel, VersionedModel, utcnow
from agent_core.contracts.evidence import SourceRef
from agent_core.contracts.governance import ApprovalTier

LHP_VERSION = "lhp.v2"
CORE_LOOPS = frozenset({"soc", "noc", "engineering", "knowledge"})

HandoffStatus = Literal[
    "proposed",
    "awaiting_approval",
    "queued",
    "claimed",
    "in_progress",
    "result_submitted",
    "verification_pending",
    "completed",
    "rejected",
    "failed",
    "cancelled",
    "expired",
]
HandoffEventType = Literal[
    "created",
    "approval_requested",
    "approved",
    "rejected",
    "queued",
    "claimed",
    "heartbeat",
    "progress",
    "result_submitted",
    "verification_pending",
    "verified",
    "failed",
    "cancelled",
    "expired",
]


def _coordination_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LoopRegistration(VersionedModel):
    """Centrally approved loop identity and capability manifest."""

    loop_id: str
    display_name: str
    capabilities: list[str] = Field(default_factory=list, max_length=100)
    environment: str = "production"
    service_name: str = ""
    host: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("loop_id")
    @classmethod
    def _loop_id(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or len(value) > 64:
            raise ValueError("loop_id must be a non-empty token of at most 64 characters")
        if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in value):
            raise ValueError("loop_id contains unsupported characters")
        return value


class LoopHeartbeat(VersionedModel):
    loop_id: str
    status: Literal["active", "idle", "degraded", "disabled"] = "active"
    summary: str = Field(default="", max_length=500)
    observed_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseProjection(VersionedModel):
    """Sanitized shared view; the owner loop retains full authoritative state."""

    case_id: str
    owner_loop: str
    version: int = Field(default=1, ge=1)
    status: str = Field(default="open", max_length=80)
    severity: str = Field(default="UNKNOWN", max_length=32)
    title: str = Field(default="", max_length=300)
    summary: str = Field(default="", max_length=2000)
    resource_id: str = Field(default="", max_length=300)
    evidence_refs: list[SourceRef] = Field(default_factory=list, max_length=40)
    opened_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffEnvelope(VersionedModel):
    """Immutable, scope-hashed request passed from one loop to another."""

    protocol_version: Literal["lhp.v2"] = "lhp.v2"
    handoff_id: str = Field(default_factory=lambda: _coordination_id("handoff"))
    work_item_id: str = ""
    case_id: str = ""
    source_loop: str
    target_loop: str
    capability: str = Field(min_length=1, max_length=160)
    intent: str = Field(default="", max_length=1000)
    summary: str = Field(default="", max_length=2000)
    risk_level: RiskLevel = "low"
    approval_tier: ApprovalTier = "none"
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_ref: str = Field(default="", max_length=500)
    evidence_refs: list[SourceRef] = Field(default_factory=list, max_length=40)
    context_refs: list[SourceRef] = Field(default_factory=list, max_length=40)
    constraints: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(default="", max_length=180)
    causation_id: str = Field(default="", max_length=180)
    run_id: str = Field(default="", max_length=180)
    trace_id: str = Field(default="", max_length=180)
    idempotency_key: str = Field(min_length=1, max_length=180)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    scope_hash: str = ""

    @field_validator("source_loop", "target_loop")
    @classmethod
    def _loop(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or len(value) > 64:
            raise ValueError("loop identity must be a non-empty token")
        return value

    @model_validator(mode="after")
    def _scope(self) -> HandoffEnvelope:
        if self.source_loop == self.target_loop and self.capability != "soc.active_probe.rt2":
            raise ValueError("self-targeted handoffs are reserved for approved SOC probe work")
        material = self.model_dump(mode="json", exclude={"scope_hash", "created_at"})
        expected = _canonical_hash(material)
        if self.scope_hash and self.scope_hash != expected:
            raise ValueError("scope_hash does not match the canonical handoff scope")
        self.scope_hash = expected
        return self


class HandoffEvent(VersionedModel):
    event_id: str = Field(default_factory=lambda: _coordination_id("hevt"))
    handoff_id: str
    event_type: HandoffEventType
    actor_id: str
    actor_loop: str = ""
    from_status: HandoffStatus | None = None
    to_status: HandoffStatus
    handoff_version: int = Field(ge=1)
    summary: str = Field(default="", max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class HandoffResult(VersionedModel):
    handoff_id: str
    result_id: str = Field(default_factory=lambda: _coordination_id("result"))
    outcome: Literal["succeeded", "partial", "failed", "rejected"]
    summary: str = Field(default="", max_length=2000)
    evidence_refs: list[SourceRef] = Field(default_factory=list, max_length=40)
    artifact_refs: list[SourceRef] = Field(default_factory=list, max_length=40)
    payload: dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=utcnow)


class VerificationResult(VersionedModel):
    handoff_id: str
    verification_id: str = Field(default_factory=lambda: _coordination_id("verify"))
    verdict: Literal["passed", "failed", "pending"]
    summary: str = Field(default="", max_length=2000)
    evidence_refs: list[SourceRef] = Field(default_factory=list, max_length=40)
    consecutive_passes: int = Field(default=0, ge=0)
    required_consecutive_passes: int = Field(default=1, ge=1)
    verified_at: datetime = Field(default_factory=utcnow)


class ApprovalRecord(VersionedModel):
    approval_id: str = Field(default_factory=lambda: _coordination_id("approval"))
    handoff_id: str
    scope_hash: str = Field(min_length=64, max_length=64)
    decision: Literal["approved", "rejected"]
    approver_id: str
    approver_login: str = ""
    approver_role: Literal["operator", "senior"]
    rationale: str = Field(default="", max_length=2000)
    decided_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None


class HandoffRecord(VersionedModel):
    envelope: HandoffEnvelope
    status: HandoffStatus
    version: int = Field(default=1, ge=1)
    claim_owner: str = ""
    lease_expires_at: datetime | None = None
    result: HandoffResult | None = None
    verification: VerificationResult | None = None
    approval: ApprovalRecord | None = None
    updated_at: datetime = Field(default_factory=utcnow)


class ProbePlan(VersionedModel):
    """Bounded RT-2 plan.  The coordinator approval binds its serialized hash."""

    probe_kind: Literal[
        "tcp_connect_sweep",
        "tls_handshake",
        "http_headers",
        "dns_consistency",
    ]
    targets: list[str] = Field(min_length=1, max_length=3)
    ports: list[int] = Field(default_factory=list, max_length=32)
    max_concurrency: int = Field(default=2, ge=1, le=2)
    requests_per_second_per_target: float = Field(default=1.0, gt=0, le=1.0)
    max_requests: int = Field(default=100, ge=1, le=100)
    max_duration_seconds: int = Field(default=600, ge=1, le=600)
    allow_redirects: bool = False
    approved_asset_refs: list[SourceRef] = Field(min_length=1, max_length=20)

    @field_validator("ports")
    @classmethod
    def _ports(cls, value: list[int]) -> list[int]:
        if any(port < 1 or port > 65535 for port in value):
            raise ValueError("ports must be between 1 and 65535")
        if len(set(value)) != len(value):
            raise ValueError("ports must be unique")
        return value

    @model_validator(mode="after")
    def _probe_shape(self) -> ProbePlan:
        if self.probe_kind in {"tcp_connect_sweep", "tls_handshake"} and not self.ports:
            raise ValueError(f"{self.probe_kind} requires explicit ports")
        return self


def default_lease_expiry(seconds: int = 120) -> datetime:
    return utcnow() + timedelta(seconds=max(30, min(seconds, 900)))
