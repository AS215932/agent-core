"""Map engineering-loop shapes -> agent-core contracts (no runtime wiring).

Source shapes: hyrule_engineering_loop.state.GraphState, llm.RoleReviewOutput /
FileMutation, backend CostReport (in backend_results[].cost), trace.loop_trace.json.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from agent_core.contracts.decision import DecisionPacket
from agent_core.contracts.models import CostUsage
from agent_core.contracts.observatory import ObservatoryLink
from agent_core.contracts.task import TaskEnvelope
from agent_core.contracts.tools import ToolResult
from agent_core.contracts.tracing import TraceEvent

GRAPH_ID = "engineering-loop"
_GITHUB_PR_RE = re.compile(r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)")


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
    """Convert Engineering Loop trace/state dictionaries to observatory TraceEvents.

    Besides legacy LLM/gate/backend summaries, this emits one ``loop_node`` event for
    each compact graph-node trace item when ``trace_events`` (live state) or ``events``
    (``loop_trace.json``) is present. Events carry change/repository/PR correlation so
    the observatory can stitch graph actions, GitHub artifacts, and deploy evidence
    into a single safe traceback.
    """
    events: list[TraceEvent] = []
    base_fields = _base_trace_fields(trace, run_id=run_id)
    previous_event_id: str | None = None

    for item in trace.get("llm_outputs", []) or []:
        event = TraceEvent.model_validate(
            {
                **base_fields,
                "event_type": "model_call",
                "node_id": item.get("role"),
                "agent_role": item.get("role"),
                "summary": f"role review approved={item.get('approved')}",
                "payload": item,
            }
        )
        events.append(event)
        previous_event_id = event.event_id
    for gate in trace.get("gate_results", []) or []:
        event = TraceEvent.model_validate(
            {
                **base_fields,
                "event_type": "tool_call",
                "node_id": "gate_execution",
                "summary": str(gate.get("command")),
                "payload": gate,
                "parent_event_id": previous_event_id,
            }
        )
        events.append(event)
        previous_event_id = event.event_id
    for backend_result in trace.get("backend_results", []) or []:
        event = TraceEvent.model_validate(
            {
                **base_fields,
                "repository": _repo_from_backend(backend_result) or base_fields.get("repository"),
                "event_type": "backend_execution",
                "node_id": "delegate_implementation",
                "summary": (
                    f"backend={backend_result.get('backend')} "
                    f"status={backend_result.get('status')}"
                ),
                "payload": backend_result,
                "cost": cost_usage_from_backend_result(backend_result).model_dump(),
                "parent_event_id": previous_event_id,
            }
        )
        events.append(event)
        previous_event_id = event.event_id

    node_trace = trace.get("trace_events") or trace.get("events") or []
    for item in node_trace:
        if not isinstance(item, Mapping):
            continue
        event = TraceEvent.model_validate(
            {
                **base_fields,
                "event_type": "loop_node",
                "node_id": _string_or_none(item.get("node")),
                "agent_role": _string_or_none(item.get("role")),
                "summary": _node_summary(item),
                "payload": _bounded_node_payload(item),
                "parent_event_id": previous_event_id,
            }
        )
        events.append(event)
        previous_event_id = event.event_id

    return events


def _base_trace_fields(trace: Mapping[str, Any], *, run_id: str | None) -> dict[str, Any]:
    raw_change = trace.get("change")
    change: Mapping[str, Any] = raw_change if isinstance(raw_change, Mapping) else {}
    change_id = _string_or_none(trace.get("change_id") or change.get("change_id") or run_id)
    pr_url = _string_or_none(
        trace.get("pr_url") or trace.get("github_pr_url") or _nested(trace, "github", "url")
    )
    fields: dict[str, Any] = {
        "run_id": run_id,
        "graph_id": GRAPH_ID,
        "change_id": change_id,
        "repository": _repository_from_trace(trace, pr_url=pr_url),
        "pr_number": _int_or_none(
            trace.get("pr_number")
            or _nested(trace, "github", "number")
            or _pr_number_from_url(pr_url)
        ),
        "commit_sha": _string_or_none(
            trace.get("commit_sha")
            or trace.get("remote_commit")
            or trace.get("commit")
            or _nested(trace, "github", "commit")
        ),
        "workflow_run_id": _string_or_none(
            trace.get("workflow_run_id") or trace.get("github_run_id")
        ),
        "links": _links(trace, pr_url=pr_url),
    }
    return fields


def _repository_from_trace(trace: Mapping[str, Any], *, pr_url: str | None) -> str | None:
    direct = _string_or_none(trace.get("repository") or trace.get("feature_target_repo"))
    if direct:
        return direct
    match = _GITHUB_PR_RE.search(pr_url or "")
    if match:
        return f"{match.group('owner')}/{match.group('repo')}"
    names = trace.get("promotion_repo_names")
    if isinstance(names, list) and len(names) == 1:
        return _string_or_none(names[0])
    repos = trace.get("promotion_repositories")
    if isinstance(repos, Mapping) and len(repos) == 1:
        return _string_or_none(next(iter(repos)))
    return None


def _repo_from_backend(backend_result: Mapping[str, Any]) -> str | None:
    return _string_or_none(backend_result.get("repository") or backend_result.get("repo"))


def _links(trace: Mapping[str, Any], *, pr_url: str | None) -> list[ObservatoryLink]:
    links: list[ObservatoryLink] = []
    if pr_url:
        links.append(ObservatoryLink(kind="github_pr", label="Engineering Loop PR", url=pr_url))
    workflow_url = _string_or_none(trace.get("workflow_run_url") or trace.get("github_run_url"))
    if workflow_url and workflow_url != pr_url:
        links.append(ObservatoryLink(kind="workflow_run", label="Workflow run", url=workflow_url))
    return links


def _node_summary(item: Mapping[str, Any]) -> str:
    node = _string_or_none(item.get("node")) or "node"
    output = item.get("output")
    if isinstance(output, Mapping):
        status = (
            output.get("status") or output.get("promotion_status") or output.get("signoff_status")
        )
        if status:
            return f"{node} status={status}"
        if output.get("validation_errors"):
            errors = output.get("validation_errors")
            count = len(errors) if isinstance(errors, list) else 1
            return f"{node} validation_errors={count}"
    return f"{node} completed"


def _bounded_node_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "node": item.get("node"),
        "role": item.get("role"),
        "timestamp": item.get("timestamp"),
        "input_keys": item.get("input_keys", []),
        "output": item.get("output", {}),
        "state_before": item.get("state_before", {}),
    }


def _nested(mapping: Mapping[str, Any], key: str, child: str) -> Any:
    value = mapping.get(key)
    return value.get(child) if isinstance(value, Mapping) else None


def _pr_number_from_url(url: str | None) -> int | None:
    match = _GITHUB_PR_RE.search(url or "")
    return int(match.group("number")) if match else None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
