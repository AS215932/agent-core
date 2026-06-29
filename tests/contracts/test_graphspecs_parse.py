from __future__ import annotations

from pathlib import Path

import yaml

from agent_core.contracts.graph import GraphSpec

GRAPHS = Path(__file__).resolve().parents[2] / "agent_core" / "contracts" / "graphs"


def _load(name: str) -> GraphSpec:
    return GraphSpec.model_validate(yaml.safe_load((GRAPHS / name).read_text()))


def test_engineering_graph() -> None:
    spec = _load("engineering-loop.draft.graph.yaml")
    assert spec.graph_id == "engineering-loop"
    assert len(spec.nodes) == 20
    kinds = {n.id: n.kind for n in spec.nodes}
    assert kinds["human_signoff"] == "human_approval"
    assert kinds["reflection"] == "finalizer"


def test_noc_graph() -> None:
    spec = _load("noc-agent.draft.graph.yaml")
    assert len(spec.nodes) == 13
    by_id = {n.id: n for n in spec.nodes}
    assert by_id["approval_interrupt"].kind == "human_approval"
    assert by_id["execute_approved_remediation"].risk_tier == "critical"


def test_knowledge_graph() -> None:
    spec = _load("knowledge.draft.graph.yaml")
    assert spec.entrypoint == "retrieve"
    assert any(n.kind == "policy" for n in spec.nodes)
