from __future__ import annotations

from agent_core.contracts import (
    CostUsage,
    DecisionPacket,
    FeedbackEvent,
    TaskEnvelope,
    ToolResult,
    TraceEvent,
)
from agent_core.contracts._base import VersionedModel


def _roundtrip(model: VersionedModel) -> None:
    restored = type(model).model_validate_json(model.model_dump_json())
    assert restored == model


def test_roundtrips() -> None:
    _roundtrip(TaskEnvelope(task_id="t", task_class="c", source="s", risk_level="high"))
    _roundtrip(TraceEvent(event_type="x", cost=CostUsage(usd=0.5)))
    _roundtrip(ToolResult(tool="t", output={"a": 1}))
    _roundtrip(DecisionPacket(decision="approve", approved=True))
    _roundtrip(FeedbackEvent(feedback_id="f", signal_type="bad", categories=["hallucinated"]))
