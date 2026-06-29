from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_core.adapters import knowledge as kn


def test_evidence_from_context_pack(load_fixture: Callable[[str], Any]) -> None:
    pack = load_fixture("context_pack.sample.json")
    evidence = kn.evidence_from_context_pack(pack)
    assert len(evidence.sources) == 2
    assert evidence.authority_max == "A0"
    assert evidence.metadata["context_pack_id"] == "ctx_0123456789abcdef0123456789abcdef"


def test_trace_event_from_context_pack(load_fixture: Callable[[str], Any]) -> None:
    pack = load_fixture("context_pack.sample.json")
    event = kn.trace_event_from_context_pack(pack, run_id="run-2")
    assert event.event_type == "knowledge_context_pack"
    assert event.run_id == "run-2"


def test_task_envelope_deterministic() -> None:
    first = kn.task_envelope_from_context_request("same task")
    second = kn.task_envelope_from_context_request("same task")
    assert first.task_id == second.task_id
    assert first.task_id.startswith("know_")
    assert first.task_class == "knowledge_retrieval"
