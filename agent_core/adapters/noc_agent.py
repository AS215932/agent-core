"""Map NOC agent shapes -> agent-core contracts (no runtime wiring).

Source shapes: app/graph/state.py ChangeProposal / EvidenceItem / ApprovalDecision,
app/model_metrics.py.
"""

from __future__ import annotations

from typing import Any

from agent_core.contracts.approval import HumanApprovalDecision
from agent_core.contracts.decision import DecisionPacket
from agent_core.contracts.evidence import EvidencePacket
from agent_core.contracts.models import CostUsage
from agent_core.contracts.task import TaskEnvelope
from agent_core.contracts.tools import ToolResult

GRAPH_ID = "noc-agent"


def task_envelope_from_alert(
    alert: dict[str, Any],
    incident_id: str,
    resource_id: str = "",
    risk_level: str = "medium",
) -> TaskEnvelope:
    return TaskEnvelope.model_validate(
        {
            "task_id": incident_id,
            "task_class": alert.get("rule") or alert.get("alertname") or "noc_triage",
            "source": GRAPH_ID,
            "risk_level": risk_level,
            "input": {"normalized_alert": alert, "resource_id": resource_id},
            "graph_id": GRAPH_ID,
        }
    )


def tool_result_from_evidence_item(item: dict[str, Any]) -> ToolResult:
    payload = dict(item.get("payload", {}) or {})
    return ToolResult.model_validate(
        {
            "tool": item.get("tool", ""),
            "ok": True,
            "output": {
                "summary": item.get("summary"),
                "direct_measurement": item.get("direct_measurement", False),
                **payload,
            },
            "node_id": "evidence_validation",
            "graph_id": GRAPH_ID,
        }
    )


def evidence_from_items(items: list[dict[str, Any]]) -> EvidencePacket:
    return EvidencePacket.model_validate(
        {
            "tool_results": [tool_result_from_evidence_item(i).model_dump() for i in items],
            "graph_id": GRAPH_ID,
        }
    )


def decision_from_change_proposal(proposal: dict[str, Any]) -> DecisionPacket:
    remediation = [{"remediation": r} for r in proposal.get("proposed_remediation", []) or []]
    structured = list(proposal.get("structured_actions", []) or [])
    sources = [{"ref": ref} for ref in proposal.get("evidence_refs", []) or []]
    return DecisionPacket.model_validate(
        {
            "decision": "propose_remediation",
            "confidence": proposal.get("confidence"),
            "rationale": proposal.get("assessment") or proposal.get("root_cause_hypothesis", ""),
            "proposed_actions": remediation + structured,
            "evidence": {
                "sources": sources,
                "metadata": {"drift_findings": proposal.get("drift_findings", []) or []},
            },
            "node_id": "proposal_build",
            "graph_id": GRAPH_ID,
        }
    )


def approval_decision_from_noc(decision: dict[str, Any]) -> HumanApprovalDecision:
    payload: dict[str, Any] = {
        "request_id": decision.get("incident_id", ""),
        "decision": decision["decision"],
        "approver": decision.get("operator", "unknown"),
        "rationale": decision.get("comment", ""),
        "graph_id": GRAPH_ID,
    }
    if decision.get("decided_at"):
        payload["decided_at"] = decision["decided_at"]
    return HumanApprovalDecision.model_validate(payload)


def cost_usage_from_model_metrics(metrics: dict[str, Any]) -> CostUsage:
    return CostUsage.model_validate(
        {
            "model": metrics.get("model") or metrics.get("active_model"),
            "provider": metrics.get("provider"),
            "latency_ms": metrics.get("latency_ms"),
            "fallback_used": bool(metrics.get("fallback_attempts") or metrics.get("fallback_used")),
        }
    )
