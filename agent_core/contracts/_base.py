"""Base model + shared type aliases for all agent-core contracts.

Design rules (see ../../../docs/migration/first-safe-milestone.md):
- pydantic v2 only; no heavy runtime deps.
- every contract is JSON-serializable and carries ``schema_version``.
- runtime/event contracts also carry optional provenance labels.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "0.1.0"

# Shared, deliberately small vocabularies (supersets across loops).
RiskLevel = Literal["low", "medium", "high", "critical"]
ToolRiskTier = Literal["read_only", "low_write", "high_write", "prod_change"]
DifficultyBand = Literal["cheap", "balanced", "strong", "frontier"]
AuthorityTier = Literal["A0", "A1", "A2", "A3", "A4", "A5"]
ActorRole = Literal["end_user", "operator", "senior", "system"]


def utcnow() -> datetime:
    """Timezone-aware UTC now (used as default_factory)."""
    return datetime.now(UTC)


class VersionedModel(BaseModel):
    """Base for every contract: strict, schema-versioned, JSON-serializable."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION


class TraceableModel(VersionedModel):
    """Base for runtime/event contracts: adds optional provenance labels.

    Labels let any emitted object be tied back to an environment, graph version,
    node, agent role, and run/trace without coupling to a runtime.
    """

    environment: str | None = None
    graph_id: str | None = None
    graph_version: str | None = None
    node_id: str | None = None
    agent_role: str | None = None
    run_id: str | None = None
    trace_id: str | None = None
