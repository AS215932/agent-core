"""Shared loop decision contracts.

These records sit one level above the insight contract: they carry the input,
retrieved context, selected action, evidence, outcome, learning label, and
governance controls for a loop decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from agent_core.contracts._base import TraceableModel, utcnow
from agent_core.contracts.evidence import SourceRef
from agent_core.contracts.governance import GovernanceControls
from agent_core.contracts.insight import InsightAction, InsightLabel, InsightLoop


class LoopDecisionEnvelope(TraceableModel):
    """Transport-neutral record for one loop input-to-decision cycle."""

    envelope_id: str
    loop: InsightLoop
    created_at: datetime = Field(default_factory=utcnow)
    input_event: dict[str, Any] = Field(default_factory=dict)
    retrieved_context: list[SourceRef] = Field(default_factory=list)
    decision: InsightAction
    evidence_refs: list[SourceRef] = Field(default_factory=list)
    proposed_action: dict[str, Any] = Field(default_factory=dict)
    human_outcome: dict[str, Any] = Field(default_factory=dict)
    learning_label: InsightLabel | None = None
    governance: GovernanceControls = Field(default_factory=GovernanceControls)
    insight_id: str | None = None
    case_id: str | None = None
    meta_case_id: str | None = None
    fingerprint: str = ""
    policy_version: str | None = None


class CrossLoopArbiterDecision(TraceableModel):
    """Ownership/speaking decision when multiple loops see the same event."""

    arbiter_decision_id: str
    created_at: datetime = Field(default_factory=utcnow)
    event_fingerprint: str
    candidate_loops: list[InsightLoop] = Field(default_factory=list)
    owner_loop: InsightLoop | None = None
    speak_loop: InsightLoop | None = None
    selected_action: InsightAction = "stay_silent"
    related_case_ids: list[str] = Field(default_factory=list)
    merged_case_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[SourceRef] = Field(default_factory=list)
    rationale: str = ""
    governance: GovernanceControls = Field(default_factory=GovernanceControls)
    policy_version: str | None = None
