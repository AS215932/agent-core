# Builds the agent-core trace collector service image.
# Built on the host by ansible/roles/collector (docker build), mirroring knowledge-mcp.
# Run: python -m agent_core.collector (FastAPI). Set HYRULE_COLLECTOR_DATABASE_URL to a
# postgresql+asyncpg URL in production.
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:${PATH}" \
    HYRULE_COLLECTOR_BIND=0.0.0.0 \
    HYRULE_COLLECTOR_PORT=8770

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml README.md ./
COPY agent_core ./agent_core
RUN uv venv && uv pip install '.[collector]'

EXPOSE 8770
USER 65534:65534
ENTRYPOINT ["python", "-m", "agent_core.collector"]
