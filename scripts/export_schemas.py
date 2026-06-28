"""Export JSON Schemas for every public contract to agent_core/contracts/schemas/.

Run after changing contracts; CI checks the committed output is up to date.
"""

from __future__ import annotations

import json
from pathlib import Path

import agent_core.contracts as contracts
from agent_core.contracts._base import TraceableModel, VersionedModel

OUT_DIR = Path(__file__).resolve().parent.parent / "agent_core" / "contracts" / "schemas"


def model_classes() -> list[type[VersionedModel]]:
    models: list[type[VersionedModel]] = []
    for name in contracts.__all__:
        obj = getattr(contracts, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, VersionedModel)
            and obj not in (VersionedModel, TraceableModel)
        ):
            models.append(obj)
    return sorted(models, key=lambda m: m.__name__)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for model in model_classes():
        schema = model.model_json_schema()
        path = OUT_DIR / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"exported {len(model_classes())} schemas to {OUT_DIR}")


if __name__ == "__main__":
    main()
