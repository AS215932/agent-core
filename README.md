# agent-core

Shared, dependency-light **typed contracts** and optional coordination services for
the AS215932 Agent Runtime Framework.

The base installation remains contract-only; service and HTTP dependencies are isolated
behind extras:

- `agent_core/contracts/` — pydantic v2 models (JSON-serializable, schema-versioned).
  Importing them pulls in **only pydantic** (no langgraph / pydantic-ai / db).
  Includes insight-policy, loop-decision, governance, and arbiter DTOs.
- `agent_core/arbiter.py` — a deterministic first-pass cross-loop ownership helper for
  suppressing duplicate NOC/SOC/Engineering/Knowledge escalations.
- `agent_core/adapters/` — pure mapping functions that convert each loop's existing
  shapes (engineering-loop, NOC agent, knowledge) into the shared contracts. **Imported
  by tests only**; not wired into any loop's runtime.
- `agent_core/contracts/graphs/` — *descriptive* draft `GraphSpec`s of the loops' current
  LangGraph topology (no compiler yet).
- `agent_core/coordination/` — signed LHP-v2 HTTP client used identically by SOC, NOC,
  Engineering, Knowledge, and the Agentic Observatory.
- `agent_core/coordinator/` — optional FastAPI/Postgres coordination service. It owns
  handoff state, claims, immutable approvals, verification transitions, and sanitized
  case projections; it does not own private loop state or replace the trace collector.

## Scope

In: contracts, adapters, draft GraphSpecs, deterministic arbitration, the optional
coordinator/client, tests, and CI. Out: a universal agent runtime, GraphSpec compiler,
model router, tool/MCP registry, or direct production executor.

## Coordinator

```bash
uv run --extra coordinator agent-core-coordinator
```

Production requires `HYRULE_COORDINATOR_DATABASE_URL` and a JSON map of per-loop key
IDs/secrets in `HYRULE_COORDINATOR_LOOP_KEYS_JSON`. The service binds to port `8771` by
default. Every protected request is signed with the generic `X-Agent-Loop-*` headers;
the shared `CoordinatorClient` handles canonical encoding and signing.

## Develop

```bash
uv venv && uv pip install -e '.[dev]'   # or: python -m venv .venv && pip install -e '.[dev]'
ruff check . && mypy agent_core && pytest -q
python scripts/export_schemas.py        # regenerate committed JSON schemas
```

See `../docs/` for the full inventory, contract-gap analysis, and migration plan.
