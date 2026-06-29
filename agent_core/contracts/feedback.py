"""FeedbackEvent: raw human/operator/automated feedback (Learning Substrate entry)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from agent_core.contracts._base import ActorRole, TraceableModel, utcnow


class FeedbackEvent(TraceableModel):
    """Raw feedback on an answer/run/node/model.

    First source: NOC ``operator_feedback`` (recorded today, unused downstream) and
    engineering-loop curated-lesson proposals. Normalizes later into RewardSignal.
    """

    feedback_id: str
    target_type: str = "answer"
    target_id: str | None = None
    actor_id: str | None = None
    actor_role: ActorRole = "operator"
    signal_type: str = "good"
    score: float | None = None
    categories: list[str] = Field(default_factory=list)
    correction_text: str = ""
    rationale: str = ""
    promote_to_memory: bool = False
    promote_to_eval: bool = False
    promote_to_judge_alignment: bool = False
    created_at: datetime = Field(default_factory=utcnow)
