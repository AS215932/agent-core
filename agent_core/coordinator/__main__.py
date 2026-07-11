from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "agent_core.coordinator.app:app",
        host=os.environ.get("HYRULE_COORDINATOR_HOST", "127.0.0.1"),
        port=int(os.environ.get("HYRULE_COORDINATOR_PORT", "8771")),
    )


if __name__ == "__main__":
    main()
