"""Decision packet: an agent's decision, confidence, rationale, next action."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from agent_core.contracts._base import TraceableModel
from agent_core.contracts.evidence import EvidencePacket


class DecisionPacket(TraceableModel):
    """Standard agent decision output.

    Maps from engineering-loop ``RoleReviewOutput`` (approved/notes/mutations) and
    NOC ``ChangeProposal`` (assessment/root_cause/confidence/structured_actions).
    """

    decision: str
    approved: bool | None = None
    confidence: float | None = None
    rationale: str = ""
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)
    next_action: str | None = None
    evidence: EvidencePacket | None = None
