"""TaskEnvelope: the standard input wrapper for all agent tasks."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from agent_core.contracts._base import RiskLevel, TraceableModel, utcnow


class TaskEnvelope(TraceableModel):
    """Standard task input.

    Maps from engineering-loop (``change_id``/``change_class``/``risk_level``/
    ``source_of_truth_files``), NOC (``incident_id`` + ``normalized_alert`` +
    ``resource_id``), and knowledge (``task``/``role``/``risk_level``).
    """

    task_id: str
    task_class: str
    source: str
    risk_level: RiskLevel = "low"
    customer_impact: Literal["none", "possible", "expected"] | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    requested_by: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
