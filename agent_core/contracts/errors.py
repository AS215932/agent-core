"""Standard error envelope (superset of NOC SafeError + engineering-loop errors)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from agent_core.contracts._base import VersionedModel, utcnow


class ErrorEnvelope(VersionedModel):
    """Structured, serializable error shape.

    Maps from NOC ``SafeError(category, public_message, operator_next_steps)`` and
    engineering-loop ``*Error`` RuntimeError subclasses.
    """

    error_type: str
    message: str
    category: str | None = None
    public_message: str | None = None
    retryable: bool = False
    operator_next_steps: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utcnow)
