"""Trace sinks: deliver TraceEvents to a JSONL file and/or an HTTP collector.

stdlib-only (``urllib``) so importing this stays dependency-light. Every sink is
best-effort: ``emit`` never raises and returns True on success, False otherwise.
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from typing import Protocol, runtime_checkable

from agent_core.contracts.tracing import TraceEvent

_TRUTHY = {"1", "true", "yes", "on"}


@runtime_checkable
class TraceSink(Protocol):
    def emit(self, event: TraceEvent) -> bool:
        """Deliver one event; return True on success. Must never raise."""
        ...


class NullSink:
    """Drops events (used when emission is disabled)."""

    def emit(self, event: TraceEvent) -> bool:
        return False


class JsonlFileSink:
    """Appends one JSON line per event to a file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def emit(self, event: TraceEvent) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
            return True
        except Exception:
            return False


class HttpSink:
    """POSTs each event as JSON to a collector URL (best-effort)."""

    def __init__(self, url: str, *, timeout: float = 2.0, token: str | None = None) -> None:
        self.url = url
        self.timeout = timeout
        self.token = token

    def emit(self, event: TraceEvent) -> bool:
        try:
            payload = event.model_dump_json().encode("utf-8")
            headers = {"content-type": "application/json"}
            if self.token:
                headers["authorization"] = f"Bearer {self.token}"
            request = urllib.request.Request(
                self.url, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                code = response.getcode()
            return bool(code is not None and 200 <= code < 300)
        except Exception:
            return False


class MultiSink:
    """Fans an event out to several sinks; True if any delivery succeeds."""

    def __init__(self, sinks: list[TraceSink]) -> None:
        self.sinks = sinks

    def emit(self, event: TraceEvent) -> bool:
        delivered = False
        for sink in self.sinks:
            if sink.emit(event):
                delivered = True
        return delivered


def sink_from_env(flag_env: str) -> TraceSink:
    """Build a sink from env vars keyed off ``flag_env``.

    ``{flag_env}`` truthy enables emission. ``{flag_env}_COLLECTOR_URL`` adds an HTTP sink
    (optional ``{flag_env}_COLLECTOR_TOKEN``); ``{flag_env}_PATH`` adds a JSONL file sink.
    Both configured -> MultiSink. Disabled or neither configured -> NullSink.
    """
    if os.environ.get(flag_env, "").strip().lower() not in _TRUTHY:
        return NullSink()
    sinks: list[TraceSink] = []
    url = os.environ.get(f"{flag_env}_COLLECTOR_URL", "").strip()
    if url:
        token = os.environ.get(f"{flag_env}_COLLECTOR_TOKEN") or None
        sinks.append(HttpSink(url, token=token))
    path = os.environ.get(f"{flag_env}_PATH", "").strip()
    if path:
        sinks.append(JsonlFileSink(path))
    if not sinks:
        return NullSink()
    if len(sinks) == 1:
        return sinks[0]
    return MultiSink(sinks)
