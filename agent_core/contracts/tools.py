"""Tool contracts: definition (ToolContract) and result envelope (ToolResult)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from agent_core.contracts._base import ToolRiskTier, TraceableModel, VersionedModel
from agent_core.contracts.errors import ErrorEnvelope
from agent_core.contracts.models import CostUsage


class ToolContract(VersionedModel):
    """Typed declaration of a tool (or MCP tool) the runtime may execute."""

    name: str
    version: str = "1"
    risk_tier: ToolRiskTier = "read_only"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float | None = None
    rate_limit: dict[str, Any] = Field(default_factory=dict)
    side_effects: str | None = None
    audit_level: str = "standard"
    owner: str | None = None


class ToolResult(TraceableModel):
    """Standard envelope for the result of any tool/MCP invocation."""

    tool: str
    ok: bool = True
    output: dict[str, Any] = Field(default_factory=dict)
    error: ErrorEnvelope | None = None
    latency_ms: float | None = None
    cost: CostUsage | None = None
    permission_decision: str | None = None
    approval_decision: str | None = None
