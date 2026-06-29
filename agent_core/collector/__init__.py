"""Optional FastAPI trace collector. Install the ``collector`` extra to use it."""

from __future__ import annotations

from agent_core.collector.app import create_app

__all__ = ["create_app"]
