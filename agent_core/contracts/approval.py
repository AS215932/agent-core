"""Human approval + policy gate contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from agent_core.contracts._base import RiskLevel, TraceableModel, utcnow


class HumanApprovalRequest(TraceableModel):
    """A pause/approval request raised at a graph interrupt."""

    request_id: str
    reason: str
    risk_level: RiskLevel = "low"
    required_role: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None


class HumanApprovalDecision(TraceableModel):
    """An operator's approval/rejection. Maps from NOC ``ApprovalDecision``."""

    request_id: str
    decision: Literal["approved", "rejected", "acknowledged"]
    approver: str
    approver_role: str | None = None
    rationale: str = ""
    decided_at: datetime = Field(default_factory=utcnow)


class PolicyGateResult(TraceableModel):
    """Structured safety/approval gate decision."""

    allow: bool
    require_human_approval: bool = False
    require_stronger_judge: bool = False
    require_more_evidence: bool = False
    require_runbook: bool = False
    require_ticket_link: bool = False
    reason: str = ""
    audit: dict[str, Any] = Field(default_factory=dict)
