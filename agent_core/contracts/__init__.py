"""agent-core contracts — import pulls in pydantic only (no heavy runtime deps)."""

from __future__ import annotations

from agent_core.contracts._base import (
    SCHEMA_VERSION,
    ActorRole,
    AuthorityTier,
    DifficultyBand,
    RiskLevel,
    ToolRiskTier,
    TraceableModel,
    VersionedModel,
    utcnow,
)
from agent_core.contracts.approval import (
    HumanApprovalDecision,
    HumanApprovalRequest,
    PolicyGateResult,
)
from agent_core.contracts.context import RunContext, RuntimeContext
from agent_core.contracts.decision import DecisionPacket
from agent_core.contracts.errors import ErrorEnvelope
from agent_core.contracts.evidence import EvidencePacket, SourceRef
from agent_core.contracts.feedback import FeedbackEvent
from agent_core.contracts.graph import EdgeMode, EdgeSpec, GraphSpec, NodeKind, NodeSpec
from agent_core.contracts.models import CostUsage, ModelPolicy, RoutingDecision
from agent_core.contracts.observatory import (
    ActorRef,
    CaseSummary,
    ChangeImpactReport,
    ChangeRef,
    HandoffSummary,
    ImpactWindow,
    KnowledgeArtifactSummary,
    LoopDescriptor,
    LoopRuntimeSnapshot,
    LoopTopology,
    MetricDelta,
    ObservatoryActionRequest,
    ObservatoryActionResult,
    ObservatoryLink,
    ObservatorySnapshot,
    OutcomeSummary,
    RunSummary,
    ScoreComponent,
    TimelineItem,
    TopologyEdge,
    TopologyNode,
    VerificationObjectiveSummary,
)
from agent_core.contracts.state import AgentState
from agent_core.contracts.task import TaskEnvelope
from agent_core.contracts.tools import ToolContract, ToolResult
from agent_core.contracts.tracing import AuditEvent, TraceEvent

__all__ = [
    # base
    "SCHEMA_VERSION",
    "ActorRole",
    "AuthorityTier",
    "DifficultyBand",
    "RiskLevel",
    "ToolRiskTier",
    "TraceableModel",
    "VersionedModel",
    "utcnow",
    # core
    "TaskEnvelope",
    "AgentState",
    "RunContext",
    "RuntimeContext",
    "TraceEvent",
    "AuditEvent",
    "CostUsage",
    "ModelPolicy",
    "RoutingDecision",
    "ToolContract",
    "ToolResult",
    "SourceRef",
    "EvidencePacket",
    "DecisionPacket",
    "HumanApprovalRequest",
    "HumanApprovalDecision",
    "PolicyGateResult",
    "FeedbackEvent",
    "ErrorEnvelope",
    # observatory
    "ObservatoryLink",
    "ActorRef",
    "LoopDescriptor",
    "LoopRuntimeSnapshot",
    "RunSummary",
    "TimelineItem",
    "CaseSummary",
    "HandoffSummary",
    "VerificationObjectiveSummary",
    "KnowledgeArtifactSummary",
    "OutcomeSummary",
    "TopologyNode",
    "TopologyEdge",
    "LoopTopology",
    "ChangeRef",
    "ImpactWindow",
    "MetricDelta",
    "ScoreComponent",
    "ChangeImpactReport",
    "ObservatoryActionRequest",
    "ObservatoryActionResult",
    "ObservatorySnapshot",
    # graph (draft)
    "GraphSpec",
    "NodeSpec",
    "EdgeSpec",
    "NodeKind",
    "EdgeMode",
]
