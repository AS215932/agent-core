from __future__ import annotations

import json
from pathlib import Path

import agent_core.contracts as contracts
from agent_core.contracts._base import TraceableModel, VersionedModel

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "agent_core" / "contracts" / "schemas"


def _models() -> list[type[VersionedModel]]:
    out: list[type[VersionedModel]] = []
    for name in contracts.__all__:
        obj = getattr(contracts, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, VersionedModel)
            and obj not in (VersionedModel, TraceableModel)
        ):
            out.append(obj)
    return out


def test_committed_schemas_exist_and_match() -> None:
    assert SCHEMA_DIR.exists(), "run scripts/export_schemas.py"
    for model in _models():
        path = SCHEMA_DIR / f"{model.__name__}.schema.json"
        assert path.exists(), f"missing schema for {model.__name__}; run scripts/export_schemas.py"
        committed = json.loads(path.read_text())
        assert committed == model.model_json_schema(), f"stale schema for {model.__name__}"
