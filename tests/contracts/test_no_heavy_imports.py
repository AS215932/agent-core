from __future__ import annotations

import importlib
import sys

HEAVY = ["langgraph", "pydantic_ai", "sqlalchemy", "langchain", "redis", "asyncpg"]


def test_contracts_import_is_dependency_light() -> None:
    for mod in HEAVY:
        sys.modules.pop(mod, None)
    importlib.import_module("agent_core.contracts")
    leaked = [m for m in HEAVY if m in sys.modules]
    assert not leaked, f"contracts pulled in heavy deps: {leaked}"
