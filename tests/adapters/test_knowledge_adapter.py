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
    pack.update({"case_id": "case_1", "handoff_id": "handoff_1", "objective_id": "objective_1"})
    event = kn.trace_event_from_context_pack(pack, run_id="run-2")
    assert event.event_type == "knowledge_context_pack"
    assert event.run_id == "run-2"
    assert event.trace_id == pack["id"]
    assert event.case_id == "case_1"
    assert event.handoff_id == "handoff_1"
    assert event.objective_id == "objective_1"
    assert event.change_id == pack["task_id"]
    assert event.repository == "network-operations"
    assert event.commit_sha == "deadbeef"
    assert event.links


def test_task_envelope_deterministic() -> None:
    first = kn.task_envelope_from_context_request("same task")
    second = kn.task_envelope_from_context_request("same task")
    assert first.task_id == second.task_id
    assert first.task_id.startswith("know_")
    assert first.task_class == "knowledge_retrieval"


def test_source_ref_from_knowledge_citation() -> None:
    citation = {
        "doc_id": "curated/postmortems/noc-bgp-snapshot-root-filesystem-2026-06-30",
        "doc_path": "okf/curated/postmortems/noc-bgp-snapshot-root-filesystem-2026-06-30.md",
        "review_status": "reviewed",
        "authority": "canonical",
        "section": "Impact",
        "repo_revision": "deadbeefcafe",
        "export_version": "run_1:retr_2:pol_3",
        "score": 0.91,
        "authoritative": True,
    }
    ref = kn.source_ref_from_knowledge_citation(citation)
    assert ref.ref == "curated/postmortems/noc-bgp-snapshot-root-filesystem-2026-06-30"
    assert ref.kind == "okf_concept"
    assert ref.raw_ref == citation["doc_path"]
    assert ref.authority == "A1"
    assert ref.commit_sha == "deadbeefcafe"
    assert ref.review_status == "reviewed"
    assert ref.excerpt == "Impact"


def test_source_ref_from_knowledge_citation_tier_passthrough_and_unknown() -> None:
    def _authority(word: str) -> str | None:
        return kn.source_ref_from_knowledge_citation({"doc_id": "x", "authority": word}).authority

    assert _authority("A0") == "A0"
    assert _authority("advisory") == "A4"
    assert _authority("weird") is None
    assert kn.source_ref_from_knowledge_citation({}).ref == ""


def test_source_ref_authority_proposed_maps_to_a4() -> None:
    ref = kn.source_ref_from_knowledge_citation({"doc_id": "x", "authority": "proposed"})
    assert ref.authority == "A4"
