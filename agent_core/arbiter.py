"""Deterministic cross-loop ownership arbitration."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any

from agent_core.contracts import CrossLoopArbiterDecision, InsightLoop, SourceRef

_OWNER_PRIORITY: tuple[InsightLoop, ...] = ("soc", "noc", "engineering", "knowledge")

# Hints are matched as whole tokens (see _matches), so short hints like
# "pull_request" cannot fire inside unrelated words ("proactive", "proposed").
_SOC_HINTS = {"security", "control_drift", "posture", "attack", "abuse", "detection"}
_NOC_HINTS = {"availability", "hotspot", "alert", "infra", "network", "routing", "disk"}
_ENGINEERING_HINTS = {
    "approved_queue",
    "github_issue",
    "implementation",
    "code",
    "github_pr",
    "pull_request",
}
_KNOWLEDGE_HINTS = {
    "context",
    "context_pack",
    "citation",
    "memory",
    "learning_ledger",
    "knowledge_gap",
    "promotion",
}
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def arbitrate_cross_loop_event(
    *,
    event_fingerprint: str,
    candidates: Iterable[dict[str, Any]],
    evidence_refs: Iterable[SourceRef | dict[str, Any]] = (),
    policy_version: str = "cross-loop-arbiter.v1",
) -> CrossLoopArbiterDecision:
    """Pick one loop to own and speak for a shared event.

    The first implementation is deliberately deterministic and conservative.
    It assigns ownership from candidate type/source hints, then falls back to a
    fixed priority so duplicate escalation is stable.
    """

    rows = [dict(candidate) for candidate in candidates]
    loops: list[InsightLoop] = []
    for row in rows:
        loop = _loop(row.get("loop"))
        if loop is not None:
            loops.append(loop)
    owner = _owner_from_hints(rows) or _first_by_priority(loops)
    selected_action = "stay_silent"
    if owner is not None:
        selected_action = _selected_action_for_owner(rows, owner)
    return CrossLoopArbiterDecision(
        arbiter_decision_id=_arbiter_id(event_fingerprint, loops, owner),
        event_fingerprint=event_fingerprint,
        candidate_loops=sorted(set(loops), key=_OWNER_PRIORITY.index),
        owner_loop=owner,
        speak_loop=owner if selected_action != "stay_silent" else None,
        selected_action=selected_action,
        related_case_ids=_related_case_ids(rows),
        merged_case_refs=[f"case_graph:{event_fingerprint}"],
        evidence_refs=[SourceRef.model_validate(ref) for ref in evidence_refs],
        rationale=_rationale(owner),
        policy_version=policy_version,
    )


def _loop(value: Any) -> InsightLoop | None:
    text = str(value or "")
    return text if text in _OWNER_PRIORITY else None


def _owner_from_hints(rows: list[dict[str, Any]]) -> InsightLoop | None:
    # Aggregate hint text across ALL candidates per loop: duplicate escalations
    # from one loop must not erase an earlier row's evidence.
    by_loop: dict[InsightLoop | None, list[str]] = {}
    for row in rows:
        by_loop.setdefault(_loop(row.get("loop")), []).append(_hint_text(row))
    if _matches(" ".join(by_loop.get("soc", [])), _SOC_HINTS):
        return "soc"
    if _matches(" ".join(by_loop.get("noc", [])), _NOC_HINTS):
        return "noc"
    if _matches(" ".join(by_loop.get("engineering", [])), _ENGINEERING_HINTS):
        return "engineering"
    if _matches(" ".join(by_loop.get("knowledge", [])), _KNOWLEDGE_HINTS):
        return "knowledge"
    return None


def _hint_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "").lower()
        for key in ("candidate_type", "candidate_source", "why_now", "proposed_action")
    )


def _matches(text: str, hints: set[str]) -> bool:
    return bool(set(_TOKEN_RE.findall(text)) & hints)


def _first_by_priority(loops: list[InsightLoop]) -> InsightLoop | None:
    for loop in _OWNER_PRIORITY:
        if loop in loops:
            return loop
    return None


def _selected_action_for_owner(rows: list[dict[str, Any]], owner: InsightLoop) -> str:
    """The owner loop's chosen action, reconciled across its candidate rows.

    Accepts both InsightDecisionRecord shapes (``action_selected``) and raw
    LoopDecisionEnvelope shapes (``decision``). A surfaced choice from any
    owner row wins over quiet samples — duplicate escalation replays must not
    let a stay_silent row mute an escalation the loop actually made."""
    for row in rows:
        if _loop(row.get("loop")) != owner:
            continue
        action = str(row.get("action_selected") or row.get("decision") or "stay_silent")
        if action in {"notify", "question", "draft"}:
            return action
    return "stay_silent"


def _related_case_ids(rows: list[dict[str, Any]]) -> list[str]:
    case_ids: list[str] = []
    for row in rows:
        for key in ("case_id", "meta_case_id"):
            value = str(row.get(key) or "")
            if value and value not in case_ids:
                case_ids.append(value)
    return case_ids


def _arbiter_id(event_fingerprint: str, loops: list[InsightLoop], owner: InsightLoop | None) -> str:
    raw = "|".join([event_fingerprint, ",".join(sorted(set(loops))), str(owner or "")])
    return f"arb_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _rationale(owner: InsightLoop | None) -> str:
    if owner == "soc":
        return "SOC owns security posture, control drift, attack-path, and abuse events."
    if owner == "noc":
        return "NOC owns availability, network, routing, and infrastructure-health events."
    if owner == "engineering":
        return "Engineering owns approved implementation and PR-producing work."
    if owner == "knowledge":
        return "Knowledge owns context, citation, memory, and learning-ledger work."
    return "No candidate loop could be assigned ownership."
