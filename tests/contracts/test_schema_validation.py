from __future__ import annotations

from agent_core.contracts import (
    CostUsage,
    DecisionPacket,
    ErrorEnvelope,
    EvidencePacket,
    FeedbackEvent,
    HumanApprovalDecision,
    PolicyGateResult,
    RunContext,
    TaskEnvelope,
    ToolContract,
    ToolResult,
    TraceEvent,
)
from agent_core.contracts._base import SCHEMA_VERSION


def test_task_envelope_minimal() -> None:
    t = TaskEnvelope(task_id="t1", task_class="noc_triage", source="noc-agent")
    assert t.schema_version == SCHEMA_VERSION
    assert t.risk_level == "low"


def test_trace_event_carries_cost() -> None:
    e = TraceEvent(event_type="model_call", cost=CostUsage(usd=0.01, model="m"))
    assert e.event_id.startswith("evt_")
    assert e.cost is not None and e.cost.usd == 0.01


def test_tool_contract_and_result() -> None:
    c = ToolContract(name="net_ping", risk_tier="read_only")
    r = ToolResult(tool="net_ping", ok=True, output={"rtt_ms": 1.2})
    assert c.risk_tier == "read_only"
    assert r.ok


def test_decision_and_evidence() -> None:
    d = DecisionPacket(decision="approve", approved=True, evidence=EvidencePacket())
    assert d.approved is True
    assert d.evidence is not None


def test_other_core_models() -> None:
    assert RunContext(run_id="r1").run_id == "r1"
    assert ErrorEnvelope(error_type="X", message="boom").retryable is False
    assert PolicyGateResult(allow=False).allow is False
    assert FeedbackEvent(feedback_id="f1").actor_role == "operator"
    approval = HumanApprovalDecision(request_id="i1", decision="approved", approver="op")
    assert approval.decision == "approved"
