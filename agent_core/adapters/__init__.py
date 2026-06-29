"""Adapters: pure mapping functions from each loop's shapes to agent-core contracts.

These are imported by tests only — they are NOT wired into any loop's runtime in this
milestone. Each function takes a JSON-serializable dict (the loop's existing shape) and
returns a typed contract.
"""

from __future__ import annotations

from agent_core.adapters import engineering_loop, knowledge, noc_agent

__all__ = ["engineering_loop", "knowledge", "noc_agent"]
