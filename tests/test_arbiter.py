from __future__ import annotations

from agent_core.arbiter import arbitrate_cross_loop_event


def test_arbiter_assigns_soc_for_security_posture_duplicate() -> None:
    decision = arbitrate_cross_loop_event(
        event_fingerprint="shared-security-drift",
        candidates=[
            {
                "loop": "noc",
                "candidate_type": "hotspot",
                "candidate_source": "proactive_scanner",
                "action_selected": "notify",
                "case_id": "case_noc_1",
            },
            {
                "loop": "soc",
                "candidate_type": "control_drift",
                "candidate_source": "soc_posture:firewall",
                "action_selected": "notify",
                "case_id": "sec_case_1",
            },
        ],
        evidence_refs=[{"ref": "knowledge:case_graph:shared-security-drift"}],
    )

    assert decision.owner_loop == "soc"
    assert decision.speak_loop == "soc"
    assert decision.selected_action == "notify"
    assert decision.related_case_ids == ["case_noc_1", "sec_case_1"]


def test_arbiter_keeps_silent_owner_silent() -> None:
    decision = arbitrate_cross_loop_event(
        event_fingerprint="quiet",
        candidates=[
            {
                "loop": "noc",
                "candidate_type": "hotspot",
                "action_selected": "stay_silent",
            }
        ],
    )

    assert decision.owner_loop == "noc"
    assert decision.speak_loop is None
    assert decision.selected_action == "stay_silent"
