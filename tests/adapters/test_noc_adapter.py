from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_core.adapters import noc_agent as noc


def test_decision(load_fixture: Callable[[str], Any]) -> None:
    proposal = load_fixture("change_proposal.sample.json")
    decision = noc.decision_from_change_proposal(proposal)
    assert decision.confidence == 0.78
    assert len(decision.proposed_actions) == 3
    assert decision.evidence is not None
    assert len(decision.evidence.sources) == 2


def test_evidence(load_fixture: Callable[[str], Any]) -> None:
    items = load_fixture("evidence_items.sample.json")
    evidence = noc.evidence_from_items(items)
    assert len(evidence.tool_results) == 2
    assert evidence.tool_results[0].tool == "firewall_state"


def test_approval(load_fixture: Callable[[str], Any]) -> None:
    decision = load_fixture("approval_decision.sample.json")
    approval = noc.approval_decision_from_noc(decision)
    assert approval.decision == "approved"
    assert approval.approver == "operator-1"


def test_cost_from_metrics() -> None:
    cost = noc.cost_usage_from_model_metrics(
        {
            "active_model": "openrouter:deepseek/deepseek-v4-pro",
            "provider": "openrouter",
            "latency_ms": 2300.0,
            "fallback_attempts": 1,
        }
    )
    assert cost.fallback_used is True
    assert cost.latency_ms == 2300.0
