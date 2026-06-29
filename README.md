# agent-core

Shared, dependency-light **typed contracts** for the AS215932 Agent Runtime Framework.

This is the **§31 safe milestone** (Phase 1) of the framework consolidation described in
`../docs/migration/first-safe-milestone.md`. It introduces standard contracts **without
changing any existing loop's behavior**:

- `agent_core/contracts/` — pydantic v2 models (JSON-serializable, schema-versioned).
  Importing them pulls in **only pydantic** (no langgraph / pydantic-ai / db).
- `agent_core/adapters/` — pure mapping functions that convert each loop's existing
  shapes (engineering-loop, NOC agent, knowledge) into the shared contracts. **Imported
  by tests only**; not wired into any loop's runtime.
- `agent_core/contracts/graphs/` — *descriptive* draft `GraphSpec`s of the loops' current
  LangGraph topology (no compiler yet).

## Scope

In: contracts, adapters (test-only), draft GraphSpecs, tests, CI.
Out (later phases): runtime, GraphSpec compiler, model router, tool/MCP registries,
memory store, learning substrate, judges, policy gates, control-plane API/GUI.

## Develop

```bash
uv venv && uv pip install -e '.[dev]'   # or: python -m venv .venv && pip install -e '.[dev]'
ruff check . && mypy agent_core && pytest -q
python scripts/export_schemas.py        # regenerate committed JSON schemas
```

See `../docs/` for the full inventory, contract-gap analysis, and migration plan.
