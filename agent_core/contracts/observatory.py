"""Agentic Observatory DTOs shared by trace collectors, loop APIs, and UI clients.

These contracts intentionally describe *query/read models* and audited UI action
requests/results. They do not own operational state: NOC CaseService/LHP-v1 and
Agent-Core trace storage remain the authoritative sources. The observatory can
cache these shapes, render them server-side, and hand them to TypeScript
visualization islands without inventing a second state machine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field

from agent_core.contracts._base import VersionedModel, utcnow

LoopKind = Literal[
    "engineering",
    "noc",
    "knowledge",
    "soc",
    "collector",
    "observability",
    "other",
]
LoopStatus = Literal["active", "idle", "degraded", "disabled", "unknown"]
ActionStatus = Literal[
    "pending",
    "in_progress",
    "succeeded",
    "failed",
    "blocked",
    "skipped",
    "cancelled",
    "unknown",
]
TimelineItemType = Literal[
    "trace_event",
    "case_event",
    "handoff",
    "verification",
    "knowledge_artifact",
    "outcome",
    "approval",
    "pr",
    "ci",
    "deploy",
    "operator_feedback",
    "analysis",
    "other",
]
LinkKind = Literal[
    "case",
    "handoff",
    "run",
    "trace",
    "github_pr",
    "github_issue",
    "workflow_run",
    "deploy",
    "knowledge",
    "verification",
    "external",
    "other",
]
TopologyNodeKind = Literal[
    "loop",
    "service",
    "collector",
    "case",
    "handoff",
    "repository",
    "knowledge_base",
    "operator",
    "external",
    "other",
]
TopologyEdgeKind = Literal[
    "emits_trace",
    "reads",
    "writes",
    "requests_handoff",
    "updates_handoff",
    "verifies",
    "opens_pr",
    "deploys",
    "notifies",
    "depends_on",
    "other",
]
ImpactComponentKind = Literal["speed", "quality", "autonomy", "cost", "safety"]
ImpactVerdict = Literal["better", "worse", "mixed", "inconclusive"]
MetricDirection = Literal["higher_is_better", "lower_is_better", "neutral"]
Confidence = Literal["low", "medium", "high", "unknown"]


def _observatory_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ObservatoryLink(VersionedModel):
    """Bounded link/reference from an observatory DTO to its source artifact."""

    kind: LinkKind = "other"
    label: str = ""
    url: str = ""
    ref_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActorRef(VersionedModel):
    """Human, loop, service, or system actor shown in audit/timeline UI."""

    actor_id: str = ""
    actor_type: Literal["operator", "loop", "service", "system", "external", "unknown"] = "unknown"
    display_name: str = ""
    role: str = ""
    loop_id: str = ""


class LoopDescriptor(VersionedModel):
    """Static-ish descriptor for one agentic loop or future loop placeholder."""

    loop_id: str
    display_name: str
    kind: LoopKind = "other"
    description: str = ""
    status: LoopStatus = "unknown"
    environment: str = "production"
    owner: str = ""
    service_name: str = ""
    host: str = ""
    trace_graph_id: str = ""
    capabilities: list[str] = Field(default_factory=list)
    input_channels: list[str] = Field(default_factory=list)
    output_channels: list[str] = Field(default_factory=list)
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoopRuntimeSnapshot(VersionedModel):
    """Current operational snapshot for one loop card on the observatory home page."""

    loop_id: str
    status: LoopStatus = "unknown"
    summary: str = ""
    active_run_id: str = ""
    active_case_id: str = ""
    active_handoff_id: str = ""
    recent_action_count: int = Field(default=0, ge=0)
    pending_action_count: int = Field(default=0, ge=0)
    failed_action_count: int = Field(default=0, ge=0)
    last_event_at: datetime | None = None
    checked_at: datetime = Field(default_factory=utcnow)
    health: dict[str, Any] = Field(default_factory=dict)
    links: list[ObservatoryLink] = Field(default_factory=list)


class RunSummary(VersionedModel):
    """Trace-backed run/cycle summary assembled from collector rows."""

    run_id: str
    loop_id: str = ""
    graph_id: str = ""
    trace_id: str = ""
    status: ActionStatus = "unknown"
    title: str = ""
    summary: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_event_at: datetime | None = None
    event_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    case_ids: list[str] = Field(default_factory=list)
    handoff_ids: list[str] = Field(default_factory=list)
    change_ids: list[str] = Field(default_factory=list)
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineItem(VersionedModel):
    """A safe, ordered event for server-rendered timelines and replay islands."""

    item_id: str = Field(default_factory=lambda: _observatory_id("tl"))
    item_type: TimelineItemType
    title: str
    summary: str = ""
    status: ActionStatus = "unknown"
    severity: Literal["critical", "high", "medium", "low", "info", "unknown"] = "unknown"
    occurred_at: datetime = Field(default_factory=utcnow)
    source_loop: str = ""
    source_system: str = ""
    actor: ActorRef | None = None
    parent_item_id: str = ""
    run_id: str = ""
    trace_event_id: str = ""
    case_id: str = ""
    handoff_id: str = ""
    objective_id: str = ""
    change_id: str = ""
    repository: str = ""
    links: list[ObservatoryLink] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class CaseSummary(VersionedModel):
    """CaseService case projection reduced to the observatory list/detail header."""

    case_id: str
    case_number: str = ""
    kind: Literal["atomic", "meta", "unknown"] = "unknown"
    status: str = ""
    severity: str = "UNKNOWN"
    title: str = ""
    summary: str = ""
    origin: str = ""
    resource_id: str = ""
    issue_url: str = ""
    opened_at: datetime | None = None
    updated_at: datetime | None = None
    resolved_at: datetime | None = None
    trace_ids: list[str] = Field(default_factory=list)
    feedback_count: int = Field(default=0, ge=0)
    handoff_count: int = Field(default=0, ge=0)
    verification_pending_count: int = Field(default=0, ge=0)
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffSummary(VersionedModel):
    """Loop Handoff Protocol state shown without exposing unbounded payloads."""

    handoff_id: str
    case_id: str
    source_loop: str = ""
    target_loop: str = ""
    objective: str = ""
    objective_key: str = ""
    status: str = ""
    owner: str = ""
    verifier: str = ""
    correlation_id: str = ""
    trace_id: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    knowledge_context_refs: list[str] = Field(default_factory=list)
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerificationObjectiveSummary(VersionedModel):
    """Machine/operator verification objective attached to a case or handoff."""

    objective_id: str
    case_id: str
    handoff_id: str = ""
    objective_key: str = ""
    objective_type: str = ""
    name: str
    description: str = ""
    required_status: str = "pass"
    status: str = "pending"
    required: bool = True
    consecutive_pass_count: int = Field(default=0, ge=0)
    required_consecutive_passes: int = Field(default=1, ge=1)
    last_checked_at: datetime | None = None
    next_check_at: datetime | None = None
    evidence_ref: str = ""
    failure_reason: str = ""
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeArtifactSummary(VersionedModel):
    """Review-gated Knowledge artifact summary attached to a case/handoff."""

    artifact_id: str
    case_id: str
    handoff_id: str = ""
    artifact_type: str = ""
    scope: str = ""
    status: str = "proposed"
    review_status: str = "pending"
    version: int = Field(default=1, ge=1)
    content_hash: str = ""
    summary: str = ""
    source_refs: list[str] = Field(default_factory=list)
    created_by: str = "knowledge"
    created_at: datetime | None = None
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutcomeSummary(VersionedModel):
    """Final or interim outcome used by learning/impact analysis."""

    outcome_id: str
    work_item_type: str = "case"
    work_item_id: str
    case_type: str = ""
    proposed_action: str = ""
    action_taken: str = ""
    agent_roles: list[str] = Field(default_factory=list)
    final_score: dict[str, float] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopologyNode(VersionedModel):
    """Node for loop topology and dependency graph visualizations."""

    node_id: str
    kind: TopologyNodeKind
    label: str
    status: LoopStatus | ActionStatus = "unknown"
    loop_id: str = ""
    summary: str = ""
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopologyEdge(VersionedModel):
    """Directed edge for loop topology and handoff/dependency graphs."""

    edge_id: str = Field(default_factory=lambda: _observatory_id("edge"))
    source_id: str
    target_id: str
    kind: TopologyEdgeKind = "other"
    label: str = ""
    status: ActionStatus = "unknown"
    summary: str = ""
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoopTopology(VersionedModel):
    """Complete graph payload with a server-renderable table fallback."""

    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChangeRef(VersionedModel):
    """A repository/PR/deploy change key used to join traces, CI, and outcomes."""

    change_key: str
    repository: str = ""
    title: str = ""
    pr_number: int | None = Field(default=None, ge=1)
    issue_number: int | None = Field(default=None, ge=1)
    commit_sha: str = ""
    workflow_run_id: str = ""
    deploy_id: str = ""
    merged_at: datetime | None = None
    deployed_at: datetime | None = None
    links: list[ObservatoryLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImpactWindow(VersionedModel):
    """Time window used by deterministic before/after analysis."""

    label: Literal["baseline", "observation", "custom"] = "custom"
    starts_at: datetime
    ends_at: datetime
    sample_size: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricDelta(VersionedModel):
    """One raw metric and its before/after delta for a change analysis."""

    metric: str
    label: str = ""
    unit: str = ""
    direction: MetricDirection = "neutral"
    baseline_value: float | None = None
    observed_value: float | None = None
    delta: float | None = None
    percent_delta: float | None = None
    confidence: Confidence = "unknown"
    rationale: str = ""


class ScoreComponent(VersionedModel):
    """Scorecard component: speed, quality, autonomy, cost, or safety."""

    component: ImpactComponentKind
    baseline_score: float | None = Field(default=None, ge=0.0, le=100.0)
    observed_score: float | None = Field(default=None, ge=0.0, le=100.0)
    delta: float | None = None
    weight: float = Field(default=1.0, ge=0.0)
    confidence: Confidence = "unknown"
    metrics: list[MetricDelta] = Field(default_factory=list)
    rationale: str = ""


class ChangeImpactReport(VersionedModel):
    """Balanced better/worse/mixed/inconclusive report for one change."""

    report_id: str = Field(default_factory=lambda: _observatory_id("impact"))
    change: ChangeRef
    verdict: ImpactVerdict = "inconclusive"
    baseline_window: ImpactWindow
    observation_window: ImpactWindow
    baseline_score: float | None = Field(default=None, ge=0.0, le=100.0)
    observed_score: float | None = Field(default=None, ge=0.0, le=100.0)
    score_delta: float | None = None
    safety_regressed: bool = False
    components: list[ScoreComponent] = Field(default_factory=list)
    evidence: list[ObservatoryLink] = Field(default_factory=list)
    narrative: str = ""
    generated_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservatoryActionRequest(VersionedModel):
    """Authenticated, CSRF-protected UI intent before source-specific dispatch."""

    action_id: str = Field(default_factory=lambda: _observatory_id("act"))
    action: str
    target_type: str
    target_id: str
    actor: ActorRef
    idempotency_key: str
    reason: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=utcnow)


class ObservatoryActionResult(VersionedModel):
    """Audited result of an observatory action after source-of-truth validation."""

    action_id: str
    status: ActionStatus
    target_type: str = ""
    target_id: str = ""
    idempotency_key: str = ""
    message: str = ""
    audit_event_id: str = ""
    case_event_id: str = ""
    links: list[ObservatoryLink] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=utcnow)


class ObservatorySnapshot(VersionedModel):
    """Home/dashboard aggregate assembled from loops, cases, runs, and analysis."""

    loops: list[LoopDescriptor] = Field(default_factory=list)
    runtime: list[LoopRuntimeSnapshot] = Field(default_factory=list)
    recent_runs: list[RunSummary] = Field(default_factory=list)
    recent_cases: list[CaseSummary] = Field(default_factory=list)
    pending_handoffs: list[HandoffSummary] = Field(default_factory=list)
    recent_analysis: list[ChangeImpactReport] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
