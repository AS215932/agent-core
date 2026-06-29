"""TraceEvent (execution events) and AuditEvent (control-plane changes)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import Field

from agent_core.contracts._base import TraceableModel, VersionedModel, utcnow
from agent_core.contracts.models import CostUsage
from agent_core.contracts.observatory import ObservatoryLink


def _event_id() -> str:
    return f"evt_{uuid4().hex}"


class TraceEvent(TraceableModel):
    """A single event emitted during execution.

    Maps from engineering-loop ``loop_trace.json`` per-node summaries and NOC
    ``traces``/``CaseEvent`` rows.
    """

    event_id: str = Field(default_factory=_event_id)
    event_type: str
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    cost: CostUsage | None = None
    timestamp: datetime = Field(default_factory=utcnow)

    # Optional observatory correlation fields. They are intentionally nullable so
    # existing producers remain backward-compatible while richer emitters can tie
    # a trace event to CaseService/LHP state, GitHub artifacts, and deploy runs.
    case_id: str | None = None
    handoff_id: str | None = None
    objective_id: str | None = None
    change_id: str | None = None
    repository: str | None = None
    pr_number: int | None = Field(default=None, ge=1)
    commit_sha: str | None = None
    workflow_run_id: str | None = None
    parent_event_id: str | None = None
    links: list[ObservatoryLink] = Field(default_factory=list)


class AuditEvent(VersionedModel):
    """Audit record for a control-plane change (graph edit, promotion, etc.)."""

    actor_id: str
    action: str
    target_type: str
    target_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utcnow)
