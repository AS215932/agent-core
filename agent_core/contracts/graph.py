"""Declarative graph specs (DRAFT models only — no compiler in this milestone)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from agent_core.contracts._base import RiskLevel, VersionedModel

NodeKind = Literal[
    "agent",
    "judge",
    "tool_executor",
    "mcp",
    "retriever",
    "memory",
    "policy",
    "human_approval",
    "subgraph",
    "parallel_council",
    "synthesizer",
    "system_node",
    "finalizer",
]

EdgeMode = Literal[
    "normal",
    "conditional",
    "parallel",
    "fallback",
    "retry",
    "approval",
    "interrupt",
    "terminal",
]


class NodeSpec(VersionedModel):
    """Declarative node spec."""

    id: str
    kind: NodeKind
    implementation: str | None = None
    agent_ref: str | None = None
    judge_ref: str | None = None
    policy_ref: str | None = None
    subgraph_ref: str | None = None
    input_contract: str | None = None
    output_contract: str | None = None
    model_policy_ref: str | None = None
    tool_bindings: list[str] = Field(default_factory=list)
    mcp_bindings: list[str] = Field(default_factory=list)
    memory_namespaces: list[str] = Field(default_factory=list)
    risk_tier: RiskLevel | None = None
    timeout_seconds: float | None = None
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class EdgeSpec(VersionedModel):
    """Declarative edge spec."""

    id: str
    source: str
    target: str
    mode: EdgeMode = "normal"
    router_ref: str | None = None
    candidates: list[str] = Field(default_factory=list)
    condition: str | dict[str, Any] | None = None
    weight: float | None = None
    enabled: bool = True
    max_attempts: int | None = None
    timeout_seconds: float | None = None
    guardrails: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphSpec(VersionedModel):
    """Declarative graph topology spec (descriptive in this milestone)."""

    graph_id: str
    version_name: str
    entrypoint: str
    description: str = ""
    owner: str | None = None
    state_schema: str | None = None
    task_schema: str | None = None
    nodes: list[NodeSpec] = Field(default_factory=list)
    edges: list[EdgeSpec] = Field(default_factory=list)
    subgraphs: list[str] = Field(default_factory=list)
    model_policies: dict[str, Any] = Field(default_factory=dict)
    judge_policies: dict[str, Any] = Field(default_factory=dict)
    tool_bindings: dict[str, Any] = Field(default_factory=dict)
    mcp_bindings: dict[str, Any] = Field(default_factory=dict)
    learning_config: dict[str, Any] = Field(default_factory=dict)
    deployment: dict[str, Any] = Field(default_factory=dict)
    risk_policy: dict[str, Any] = Field(default_factory=dict)
