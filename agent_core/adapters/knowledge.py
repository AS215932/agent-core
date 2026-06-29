"""Map knowledge loop shapes -> agent-core contracts (no runtime wiring).

Source shapes: knowledge context-pack (schema/context-pack.schema.json) + CLI request.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from agent_core.contracts.evidence import EvidencePacket
from agent_core.contracts.observatory import ObservatoryLink
from agent_core.contracts.task import TaskEnvelope
from agent_core.contracts.tracing import TraceEvent

GRAPH_ID = "knowledge"
_AUTHORITY_ORDER = ["A0", "A1", "A2", "A3", "A4", "A5"]


def task_envelope_from_context_request(
    task: str,
    role: str = "engineering_loop",
    risk_level: str = "low",
    task_id: str | None = None,
) -> TaskEnvelope:
    resolved_id = task_id or "know_" + hashlib.sha256(task.encode()).hexdigest()[:8]
    return TaskEnvelope.model_validate(
        {
            "task_id": resolved_id,
            "task_class": "knowledge_retrieval",
            "source": GRAPH_ID,
            "risk_level": risk_level,
            "input": {"task": task, "role": role},
            "graph_id": GRAPH_ID,
        }
    )


def evidence_from_context_pack(pack: dict[str, Any]) -> EvidencePacket:
    sources: list[dict[str, Any]] = []
    best: str | None = None
    for ref in pack.get("included_refs", []) or []:
        authority = ref.get("authority")
        sources.append(
            {
                "ref": ref.get("ref") or ref.get("doc_id") or ref.get("doc_path") or "",
                "authority": authority,
                "kind": ref.get("kind"),
                "commit_sha": ref.get("commit_sha"),
                "review_status": ref.get("review_status"),
            }
        )
        if authority in _AUTHORITY_ORDER and (
            best is None or _AUTHORITY_ORDER.index(authority) < _AUTHORITY_ORDER.index(best)
        ):
            best = authority
    return EvidencePacket.model_validate(
        {
            "sources": sources,
            "authority_max": best,
            "unresolved_questions": pack.get("unresolved_questions", []) or [],
            "metadata": {
                "context_pack_id": pack.get("id"),
                "retrieval_version": pack.get("retrieval_version"),
                "policy_version": pack.get("policy_version"),
                "knowledge_snapshot": pack.get("knowledge_snapshot"),
            },
            "graph_id": GRAPH_ID,
        }
    )


def trace_event_from_context_pack(
    pack: dict[str, Any], *, run_id: str | None = None
) -> TraceEvent:
    ref_count = len(pack.get("included_refs", []) or [])
    first_source = _first_source_ref(pack)
    return TraceEvent.model_validate(
        {
            "event_type": "knowledge_context_pack",
            "node_id": "context_pack",
            "agent_role": _string_or_none(pack.get("role")) or "knowledge_retriever",
            "summary": f"context pack {pack.get('id')} ({ref_count} refs)",
            "payload": {
                "id": pack.get("id"),
                "task_id": pack.get("task_id"),
                "role": pack.get("role"),
                "retrieval_version": pack.get("retrieval_version"),
                "policy_version": pack.get("policy_version"),
                "policy_decision": pack.get("policy_decision"),
                "authority_max": evidence_from_context_pack(pack).authority_max,
                "included_ref_count": ref_count,
            },
            "run_id": run_id
            or _string_or_none(pack.get("run_id") or pack.get("knowledge_snapshot")),
            "graph_id": GRAPH_ID,
            "trace_id": _string_or_none(pack.get("id")),
            "case_id": _string_or_none(pack.get("case_id")),
            "handoff_id": _string_or_none(pack.get("handoff_id")),
            "objective_id": _string_or_none(pack.get("objective_id")),
            "change_id": _string_or_none(pack.get("change_id") or pack.get("task_id")),
            "repository": first_source[0],
            "commit_sha": first_source[1],
            "links": _links_for_context_pack(pack),
        }
    )


def _links_for_context_pack(pack: Mapping[str, Any]) -> list[ObservatoryLink]:
    links = [
        ObservatoryLink(
            kind="knowledge",
            label="Context pack",
            ref_id=_string_or_none(pack.get("id")) or "",
            metadata={"knowledge_snapshot": pack.get("knowledge_snapshot")},
        )
    ]
    for ref in pack.get("included_refs", []) or []:
        if not isinstance(ref, Mapping):
            continue
        raw_ref = _string_or_none(ref.get("ref") or ref.get("doc_id") or ref.get("doc_path"))
        if raw_ref:
            links.append(
                ObservatoryLink(
                    kind="knowledge",
                    label=str(ref.get("authority") or ref.get("kind") or "knowledge ref"),
                    ref_id=raw_ref,
                    metadata={
                        "authority": ref.get("authority"),
                        "kind": ref.get("kind"),
                        "review_status": ref.get("review_status"),
                        "commit_sha": ref.get("commit_sha"),
                    },
                )
            )
    return links


def _first_source_ref(pack: Mapping[str, Any]) -> tuple[str | None, str | None]:
    fallback: tuple[str | None, str | None] = (None, None)
    for ref in pack.get("included_refs", []) or []:
        if not isinstance(ref, Mapping):
            continue
        raw_ref = _string_or_none(ref.get("ref") or ref.get("doc_id") or ref.get("doc_path"))
        if not raw_ref:
            continue
        repository = raw_ref.split(":", 1)[0] if ":" in raw_ref else None
        commit_sha = _string_or_none(ref.get("commit_sha"))
        if repository or commit_sha:
            if commit_sha:
                return repository, commit_sha
            if fallback == (None, None):
                fallback = (repository, commit_sha)
    return fallback


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
