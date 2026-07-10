from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_core.contracts import (
    CrossLoopArbiterDecision,
    GovernanceControls,
    LoopDecisionEnvelope,
)


def test_loop_decision_envelope_carries_operational_spine() -> None:
    record = LoopDecisionEnvelope(
        envelope_id="ldec_1",
        loop="soc",
        input_event={"kind": "posture_finding", "id": "secf_1"},
        retrieved_context=[{"ref": "okf:curated/policies/security-posture", "authority": "A1"}],
        decision="stay_silent",
        evidence_refs=[{"ref": "mcp:firewall_state:core-router-1", "kind": "mcp"}],
        proposed_action={"type": "case", "dry_run": True},
        governance=GovernanceControls(
            sensitivity_class="sensitive",
            approval_tier="operator",
            adversarial_review_required=True,
            learning_allowed=False,
            never_learn=True,
            policy_ids=["soc-private-insight.v1"],
        ),
        insight_id="ins_soc_1",
        fingerprint="fp",
    )

    assert record.decision == "stay_silent"
    assert record.governance.never_learn is True
    assert record.evidence_refs[0].ref == "mcp:firewall_state:core-router-1"


def test_cross_loop_arbiter_assigns_single_speaker() -> None:
    decision = CrossLoopArbiterDecision(
        arbiter_decision_id="arb_1",
        event_fingerprint="shared_event",
        candidate_loops=["noc", "soc"],
        owner_loop="soc",
        speak_loop="soc",
        selected_action="notify",
        related_case_ids=["case_noc_1", "sec_case_1"],
        merged_case_refs=["knowledge:case_graph:shared_event"],
        evidence_refs=[{"ref": "knowledge:case_graph:shared_event"}],
        rationale="Security posture drift owns this event; NOC duplicate stays silent.",
    )

    assert decision.owner_loop == "soc"
    assert decision.selected_action == "notify"


def test_loop_decision_rejects_unknown_decision() -> None:
    with pytest.raises(ValidationError):
        LoopDecisionEnvelope.model_validate(
            {
                "envelope_id": "ldec_bad",
                "loop": "noc",
                "decision": "ignore",
            }
        )
