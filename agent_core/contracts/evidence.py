"""Evidence packet: sources, tool outputs, references behind an answer/decision."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from agent_core.contracts._base import AuthorityTier, TraceableModel, VersionedModel
from agent_core.contracts.tools import ToolResult


class SourceRef(VersionedModel):
    """A cited source with optional A0-A5 authority (from the knowledge loop)."""

    ref: str
    kind: str | None = None
    authority: AuthorityTier | None = None
    commit_sha: str | None = None
    review_status: str | None = None
    excerpt: str | None = None


class EvidencePacket(TraceableModel):
    """Sources + tool outputs + references that ground a decision/answer."""

    sources: list[SourceRef] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    code_refs: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    authority_max: AuthorityTier | None = None
    unresolved_questions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
