"""Map knowledge loop shapes -> agent-core contracts (no runtime wiring).

Source shapes: knowledge context-pack (schema/context-pack.schema.json) + CLI request.
"""

from __future__ import annotations

import hashlib
from typing import Any

from agent_core.contracts.evidence import EvidencePacket
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
    return TraceEvent.model_validate(
        {
            "event_type": "knowledge_context_pack",
            "node_id": "context_pack",
            "summary": f"context pack {pack.get('id')} ({ref_count} refs)",
            "payload": {
                "id": pack.get("id"),
                "retrieval_version": pack.get("retrieval_version"),
                "policy_version": pack.get("policy_version"),
                "policy_decision": pack.get("policy_decision"),
            },
            "run_id": run_id,
            "graph_id": GRAPH_ID,
        }
    )
