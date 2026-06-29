from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_core.adapters import engineering_loop as eng


def test_task_envelope(load_fixture: Callable[[str], Any]) -> None:
    state = load_fixture("graph_state.sample.json")
    env = eng.task_envelope_from_graph_state(state)
    assert env.task_id == "chg-2026-0628-001"
    assert env.source == "engineering-loop"
    assert env.risk_level == "high"
    assert env.graph_id == "engineering-loop"


def test_decision(load_fixture: Callable[[str], Any]) -> None:
    review = load_fixture("role_review.sample.json")
    decision = eng.decision_from_role_review("security_auditor", review)
    assert decision.approved is False
    assert decision.decision == "reject"
    assert len(decision.proposed_actions) == 2
    assert decision.agent_role == "security_auditor"


def test_trace_events(load_fixture: Callable[[str], Any]) -> None:
    trace = load_fixture("loop_trace.sample.json")
    trace.update(
        {
            "change_id": "chg-2026-0628-001",
            "pr_url": "https://github.com/AS215932/network-operations/pull/318",
            "commit_sha": "abc123",
            "workflow_run_id": "28392093138",
            "trace_events": [
                {
                    "node": "hydrate_context",
                    "timestamp": "2026-06-29T00:00:00Z",
                    "output": {"status": "passed"},
                },
                {
                    "node": "gate_execution",
                    "timestamp": "2026-06-29T00:01:00Z",
                    "output": {"validation_errors": []},
                },
            ],
        }
    )
    events = eng.trace_events_from_loop_trace(trace, run_id="run-1")
    types = [e.event_type for e in events]
    assert "model_call" in types
    assert "backend_execution" in types
    assert types.count("loop_node") == 2
    backend = next(e for e in events if e.event_type == "backend_execution")
    assert backend.cost is not None
    assert backend.cost.input_tokens == 1820
    assert backend.change_id == "chg-2026-0628-001"
    assert backend.repository == "network-operations"
    assert backend.pr_number == 318
    assert backend.commit_sha == "abc123"
    assert backend.workflow_run_id == "28392093138"
    loop_node = next(e for e in events if e.event_type == "loop_node")
    assert loop_node.parent_event_id
    assert loop_node.links[0].kind == "github_pr"
    assert all(e.run_id == "run-1" for e in events)
