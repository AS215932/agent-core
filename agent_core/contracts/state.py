"""AgentState: a JSON-serializable contract anchor for loop state.

This is the *contract* shape, not a replacement for a loop's live LangGraph state
(engineering-loop ``GraphState`` TypedDict + reducers, NOC ``WorkflowState``).
Adapters project a live state into this shape; nothing here replaces those types.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from agent_core.contracts._base import TraceableModel
from agent_core.contracts.task import TaskEnvelope


class AgentState(TraceableModel):
    """Minimal, serializable view of an agent run's state."""

    task: TaskEnvelope | None = None
    status: str = "pending"
    messages: list[dict[str, Any]] = Field(default_factory=list)
    scratch: dict[str, Any] = Field(default_factory=dict)
    retries: dict[str, int] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    decision_refs: list[str] = Field(default_factory=list)
    trace_event_refs: list[str] = Field(default_factory=list)
