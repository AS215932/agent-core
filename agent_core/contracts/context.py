"""RunContext (per-run metadata) and RuntimeContext (environment-level deps)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from agent_core.contracts._base import VersionedModel, utcnow


class RunContext(VersionedModel):
    """Runtime metadata for a single run; the provenance carrier."""

    run_id: str
    trace_id: str | None = None
    environment: str | None = None
    deployment_slot: str | None = None
    graph_id: str | None = None
    graph_version: str | None = None
    node_id: str | None = None
    agent_role: str | None = None
    model_policy_ref: str | None = None
    instruction_pack_ref: str | None = None
    started_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeContext(VersionedModel):
    """Environment-level runtime dependencies/config (not per-run)."""

    environment: str = "dev"
    deployment_slot: str | None = None
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
