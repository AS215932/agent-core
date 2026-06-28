"""Model/provider contracts: cost/usage, model policy, routing decision."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from agent_core.contracts._base import (
    DifficultyBand,
    RiskLevel,
    TraceableModel,
    VersionedModel,
)


class CostUsage(VersionedModel):
    """Token/latency/cost metadata for a single model call or run.

    All fields optional: engineering-loop reports USD (``CostReport``) but not
    latency; NOC reports latency/fallback metrics but not USD.
    """

    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    usd: float | None = None
    latency_ms: float | None = None
    fallback_used: bool = False


class ModelPolicy(VersionedModel):
    """Provider-agnostic model selection policy (draft).

    Superset of engineering-loop ``model-policy.yml`` (role x tier + risk/retry
    escalation) and NOC's ``FallbackModel`` chain.
    """

    policy_ref: str
    role: str | None = None
    allowed_providers: list[str] = Field(default_factory=list)
    tiers: dict[str, Any] = Field(default_factory=dict)
    risk_overrides: dict[str, Any] = Field(default_factory=dict)
    retry_escalation: dict[str, Any] = Field(default_factory=dict)
    fallback: list[str] = Field(default_factory=list)
    objective_weights: dict[str, float] = Field(default_factory=dict)


class RoutingDecision(TraceableModel):
    """Record of a model/router selection for one run (for scorecards later)."""

    agent_role: str | None = None
    task_class: str | None = None
    difficulty_band: DifficultyBand | None = None
    risk_level: RiskLevel = "low"
    selected_model: str
    selected_provider: str | None = None
    candidate_models: list[str] = Field(default_factory=list)
    router_policy_ref: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    exploration: bool = False
