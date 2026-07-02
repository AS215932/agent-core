"""Insight-policy contracts for proactive loop decisions.

These records model the Level 3 loop decision: choose whether to notify,
question, draft, or stay silent, while preserving the denominator needed for
replay and learning metrics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from agent_core.contracts._base import RiskLevel, TraceableModel, VersionedModel, utcnow
from agent_core.contracts.evidence import SourceRef

InsightAction = Literal["notify", "question", "draft", "stay_silent"]
InsightSamplingClass = Literal["surfaced", "withheld_logged", "sampled_quiet_interval"]
InsightLoop = Literal["engineering", "noc", "knowledge", "soc"]
InsightFaithfulnessVerdict = Literal["faithful", "partially_faithful", "unsupported", "not_applicable"]


class InsightScore(VersionedModel):
    """Separated score object for benefit/cost reasoning."""

    total: float | None = None
    components: dict[str, float] = Field(default_factory=dict)
    rationale: list[str] = Field(default_factory=list)


class InsightDecisionRecord(TraceableModel):
    """Auditable proactive decision, including explicit silence."""

    insight_id: str
    loop: InsightLoop
    created_at: datetime = Field(default_factory=utcnow)
    fingerprint: str
    sampling_class: InsightSamplingClass
    candidate_type: str
    candidate_source: str
    case_id: str | None = None
    meta_case_id: str | None = None
    trace_id: str | None = None
    observation_ids: list[str] = Field(default_factory=list)
    state_snapshot_refs: list[str] = Field(default_factory=list)
    support_facts: list[str] = Field(default_factory=list)
    evidence_refs: list[SourceRef] = Field(default_factory=list)
    action_space: list[InsightAction] = Field(
        default_factory=lambda: ["notify", "question", "draft", "stay_silent"]
    )
    action_selected: InsightAction
    why_now: str = ""
    why_not_other_actions: dict[InsightAction, str] = Field(default_factory=dict)
    expected_utility: InsightScore = Field(default_factory=InsightScore)
    interruption_cost: InsightScore = Field(default_factory=InsightScore)
    confidence: float | None = None
    risk_class: RiskLevel | None = None
    policy_version: str | None = None
    tool_versions: dict[str, str] = Field(default_factory=dict)
    budget_context: dict[str, Any] = Field(default_factory=dict)
    reference_action: InsightAction | None = None
    acceptable_alternatives: list[InsightAction] = Field(default_factory=list)
    faithfulness_verdict: InsightFaithfulnessVerdict | None = None
    evidence_precision: float | None = None
    evidence_recall: float | None = None
    human_feedback: dict[str, Any] = Field(default_factory=dict)
    downstream_outcome: dict[str, Any] = Field(default_factory=dict)
    learning_event_ref: str | None = None


class InsightLabel(TraceableModel):
    """Human or fixture label used for IDQ/CGS/LL-style evaluations."""

    label_id: str
    insight_id: str
    loop: InsightLoop
    created_at: datetime = Field(default_factory=utcnow)
    reference_action: InsightAction
    acceptable_alternatives: list[InsightAction] = Field(default_factory=list)
    support_facts: list[str] = Field(default_factory=list)
    faithfulness_verdict: InsightFaithfulnessVerdict | None = None
    feedback: dict[str, Any] = Field(default_factory=dict)
    reviewer: str | None = None
