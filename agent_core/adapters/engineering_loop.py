"""Map engineering-loop shapes -> agent-core contracts (no runtime wiring).

Source shapes: hyrule_engineering_loop.state.GraphState, llm.RoleReviewOutput /
FileMutation, backend CostReport (in backend_results[].cost), trace.loop_trace.json.
"""

from __future__ import annotations

from typing import Any

from agent_core.contracts.decision import DecisionPacket
from agent_core.contracts.models import CostUsage
from agent_core.contracts.task import TaskEnvelope
from agent_core.contracts.tools import ToolResult
from agent_core.contracts.tracing import TraceEvent

GRAPH_ID = "engineering-loop"


def task_envelope_from_graph_state(state: dict[str, Any]) -> TaskEnvelope:
    return TaskEnvelope.model_validate(
        {
            "task_id": state["change_id"],
            "task_class": state.get("change_class", "mixed"),
            "source": GRAPH_ID,
            "risk_level": state.get("risk_level", "low"),
            "customer_impact": state.get("customer_impact"),
            "input": {
                "source_of_truth_files": state.get("source_of_truth_files", []),
                "feature_request": state.get("feature_request"),
            },
            "graph_id": GRAPH_ID,
        }
    )


def decision_from_role_review(role: str, review: dict[str, Any]) -> DecisionPacket:
    approved = review.get("approved")
    return DecisionPacket.model_validate(
        {
            "decision": "approve" if approved else "reject",
            "approved": approved,
            "rationale": review.get("notes", ""),
            "proposed_actions": [
                {"path": m.get("path"), "operation": m.get("operation", "create")}
                for m in review.get("proposed_mutations", []) or []
            ],
            "validation_errors": review.get("validation_errors", []) or [],
            "agent_role": role,
            "node_id": role,
            "graph_id": GRAPH_ID,
        }
    )


def cost_usage_from_backend_result(backend_result: dict[str, Any]) -> CostUsage:
    cost = backend_result.get("cost", {}) or {}
    return CostUsage.model_validate(
        {
            "model": cost.get("model") or backend_result.get("model"),
            "provider": cost.get("provider"),
            "input_tokens": cost.get("input_tokens"),
            "output_tokens": cost.get("output_tokens"),
            "usd": cost.get("usd"),
        }
    )


def tool_result_from_gate(gate: dict[str, Any]) -> ToolResult:
    return ToolResult.model_validate(
        {
            "tool": str(gate.get("command")),
            "ok": gate.get("status") == "passed",
            "output": {"status": gate.get("status"), "returncode": gate.get("returncode")},
            "node_id": "gate_execution",
            "graph_id": GRAPH_ID,
        }
    )


def trace_events_from_loop_trace(
    trace: dict[str, Any], *, run_id: str | None = None
) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    for item in trace.get("llm_outputs", []) or []:
        events.append(
            TraceEvent.model_validate(
                {
                    "event_type": "model_call",
                    "node_id": item.get("role"),
                    "agent_role": item.get("role"),
                    "summary": f"role review approved={item.get('approved')}",
                    "payload": item,
                    "run_id": run_id,
                    "graph_id": GRAPH_ID,
                }
            )
        )
    for gate in trace.get("gate_results", []) or []:
        events.append(
            TraceEvent.model_validate(
                {
                    "event_type": "tool_call",
                    "node_id": "gate_execution",
                    "summary": str(gate.get("command")),
                    "payload": gate,
                    "run_id": run_id,
                    "graph_id": GRAPH_ID,
                }
            )
        )
    for backend_result in trace.get("backend_results", []) or []:
        events.append(
            TraceEvent.model_validate(
                {
                    "event_type": "backend_execution",
                    "node_id": "delegate_implementation",
                    "summary": (
                        f"backend={backend_result.get('backend')} "
                        f"status={backend_result.get('status')}"
                    ),
                    "payload": backend_result,
                    "cost": cost_usage_from_backend_result(backend_result).model_dump(),
                    "run_id": run_id,
                    "graph_id": GRAPH_ID,
                }
            )
        )
    return events
