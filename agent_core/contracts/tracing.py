"""TraceEvent (execution events) and AuditEvent (control-plane changes)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import Field

from agent_core.contracts._base import TraceableModel, VersionedModel, utcnow
from agent_core.contracts.models import CostUsage


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


class AuditEvent(VersionedModel):
    """Audit record for a control-plane change (graph edit, promotion, etc.)."""

    actor_id: str
    action: str
    target_type: str
    target_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utcnow)
