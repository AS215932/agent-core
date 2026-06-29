from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agent_core.contracts import (
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


def _now() -> datetime:
    return datetime(2026, 6, 29, tzinfo=UTC)


def test_observatory_operational_dtos_roundtrip() -> None:
    link = ObservatoryLink(kind="trace", label="trace run", ref_id="run_1")
    actor = ActorRef(actor_id="operator", actor_type="operator", display_name="Operator")
    loop = LoopDescriptor(
        loop_id="engineering",
        display_name="Engineering Loop",
        kind="engineering",
        status="active",
        trace_graph_id="engineering-loop",
        links=[link],
    )
    runtime = LoopRuntimeSnapshot(
        loop_id="engineering",
        status="active",
        active_run_id="run_1",
        recent_action_count=3,
    )
    run = RunSummary(
        run_id="run_1",
        loop_id="engineering",
        graph_id="engineering-loop",
        status="succeeded",
        event_count=3,
        links=[link],
    )
    item = TimelineItem(
        item_type="trace_event",
        title="gate passed",
        status="succeeded",
        occurred_at=_now(),
        source_loop="engineering",
        actor=actor,
        run_id="run_1",
        trace_event_id="evt_1",
        links=[link],
    )
    snapshot = ObservatorySnapshot(
        loops=[loop],
        runtime=[runtime],
        recent_runs=[run],
        recent_cases=[CaseSummary(case_id="case_1", status="open")],
    )

    for model in (link, actor, loop, runtime, run, item, snapshot):
        restored = type(model).model_validate_json(model.model_dump_json())
        assert restored == model


@pytest.mark.parametrize(
    "model",
    [
        HandoffSummary(handoff_id="handoff_1", case_id="case_1", target_loop="engineering"),
        VerificationObjectiveSummary(
            objective_id="vo_1",
            case_id="case_1",
            name="three clean checks",
        ),
        KnowledgeArtifactSummary(artifact_id="ka_1", case_id="case_1", artifact_type="lesson"),
        OutcomeSummary(outcome_id="outcome_1", work_item_id="case_1"),
        LoopTopology(
            nodes=[TopologyNode(node_id="engineering", kind="loop", label="Engineering")],
            edges=[TopologyEdge(source_id="noc", target_id="engineering", kind="requests_handoff")],
        ),
    ],
)
def test_observatory_case_handoff_and_topology_models_roundtrip(model: object) -> None:
    restored = type(model).model_validate_json(model.model_dump_json())
    assert restored == model


def test_change_impact_report_contract() -> None:
    report = ChangeImpactReport(
        change=ChangeRef(
            change_key="AS215932/network-operations#318",
            repository="AS215932/network-operations",
        ),
        verdict="better",
        baseline_window=ImpactWindow(
            label="baseline",
            starts_at=_now(),
            ends_at=_now(),
            sample_size=7,
        ),
        observation_window=ImpactWindow(
            label="observation",
            starts_at=_now(),
            ends_at=_now(),
            sample_size=4,
        ),
        baseline_score=74.0,
        observed_score=82.0,
        score_delta=8.0,
        components=[
            ScoreComponent(
                component="quality",
                baseline_score=70.0,
                observed_score=86.0,
                delta=16.0,
                confidence="medium",
                metrics=[
                    MetricDelta(
                        metric="verification_pass_rate",
                        direction="higher_is_better",
                        baseline_value=0.8,
                        observed_value=1.0,
                        delta=0.2,
                    )
                ],
            )
        ],
    )

    assert report.verdict == "better"
    assert report.components[0].component == "quality"
    assert ChangeImpactReport.model_validate_json(report.model_dump_json()) == report


def test_observatory_action_contracts_require_valid_status_and_idempotency() -> None:
    request = ObservatoryActionRequest(
        action="ack",
        target_type="case",
        target_id="case_1",
        actor=ActorRef(actor_id="op", actor_type="operator"),
        idempotency_key="ack:case_1:op",
    )
    result = ObservatoryActionResult(
        action_id=request.action_id,
        status="succeeded",
        target_type=request.target_type,
        target_id=request.target_id,
        idempotency_key=request.idempotency_key,
    )

    assert result.action_id == request.action_id
    with pytest.raises(ValidationError):
        ObservatoryActionResult(action_id="act_1", status="not-a-real-status")
