"""Governance controls shared by loop contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_core.contracts._base import RiskLevel, VersionedModel

SensitivityClass = Literal["public", "internal", "private", "sensitive", "secret"]
ApprovalTier = Literal["none", "operator", "senior", "break_glass"]


class GovernanceControls(VersionedModel):
    """Contract-level safety controls for loop decisions and learning."""

    sensitivity_class: SensitivityClass = "internal"
    approval_tier: ApprovalTier = "none"
    risk_class: RiskLevel | None = None
    adversarial_review_required: bool = False
    learning_allowed: bool = True
    never_learn: bool = False
    policy_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
