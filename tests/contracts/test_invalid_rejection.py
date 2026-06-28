from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_core.contracts import HumanApprovalDecision, TaskEnvelope


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        TaskEnvelope.model_validate(
            {"task_id": "t", "task_class": "c", "source": "s", "bogus": 1}
        )


def test_missing_required() -> None:
    with pytest.raises(ValidationError):
        TaskEnvelope.model_validate({})


def test_bad_literal_decision() -> None:
    with pytest.raises(ValidationError):
        HumanApprovalDecision.model_validate(
            {"request_id": "i", "decision": "maybe", "approver": "op"}
        )


def test_bad_risk_level() -> None:
    with pytest.raises(ValidationError):
        TaskEnvelope.model_validate(
            {"task_id": "t", "task_class": "c", "source": "s", "risk_level": "extreme"}
        )
