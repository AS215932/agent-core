"""Run the collector: ``python -m agent_core.collector``."""

from __future__ import annotations

import os

import uvicorn

from agent_core.collector.app import create_app


def main() -> None:
    uvicorn.run(
        create_app(),
        host=os.environ.get("HYRULE_COLLECTOR_BIND", "127.0.0.1"),
        port=int(os.environ.get("HYRULE_COLLECTOR_PORT", "8770")),
    )


if __name__ == "__main__":
    main()
