from __future__ import annotations

from types import TracebackType

from fastapi.testclient import TestClient

from agent_core.collector.app import create_app


def _app(tmp_path):
    return create_app(f"sqlite+aiosqlite:///{tmp_path}/collector.db")


def test_healthz(tmp_path) -> None:
    with TestClient(_app(tmp_path)) as client:
        assert client.get("/healthz").json() == {"status": "ok"}


def test_healthz_checks_database_connectivity(tmp_path) -> None:
    class BrokenSession:
        async def __aenter__(self) -> BrokenSession:
            raise RuntimeError("database down")

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> None:
            return None

    app = _app(tmp_path)
    app.state.collector_sessionmaker = lambda: BrokenSession()
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 503
        assert response.json() == {"detail": "database unavailable"}


def test_ingest_and_read(tmp_path) -> None:
    event = {
        "event_type": "model_call",
        "summary": "hello",
        "run_id": "r1",
        "cost": {"usd": 0.02, "input_tokens": 10, "output_tokens": 5},
    }
    with TestClient(_app(tmp_path)) as client:
        resp = client.post("/v1/trace", json=event)
        assert resp.status_code == 200
        assert resp.json()["status"] == "stored"
        got = client.get("/v1/trace", params={"run_id": "r1"}).json()
        assert len(got) == 1
        assert got[0]["event_type"] == "model_call"
        assert got[0]["cost"]["usd"] == 0.02


def test_ingest_rejects_invalid(tmp_path) -> None:
    with TestClient(_app(tmp_path)) as client:
        # missing required event_type
        assert client.post("/v1/trace", json={"summary": "x"}).status_code == 422


def test_batch(tmp_path) -> None:
    events = [
        {"event_type": "tool_call", "run_id": "r2"},
        {"event_type": "node_end", "run_id": "r2"},
    ]
    with TestClient(_app(tmp_path)) as client:
        assert client.post("/v1/trace/batch", json=events).json() == {"stored": 2}
        assert len(client.get("/v1/trace", params={"run_id": "r2"}).json()) == 2


def test_observatory_query_apis(tmp_path) -> None:
    events = [
        {
            "event_type": "model_call",
            "summary": "planner produced a task spec",
            "run_id": "run-observatory-1",
            "graph_id": "engineering-loop",
            "agent_role": "planner",
            "case_id": "case_123",
            "handoff_id": "handoff_123",
            "change_id": "AS215932/agent-core#10",
            "repository": "AS215932/agent-core",
            "pr_number": 10,
            "links": [
                {
                    "kind": "github_pr",
                    "label": "agent-core#10",
                    "url": "https://github.com/AS215932/agent-core/pull/10",
                    "ref_id": "10",
                }
            ],
            "cost": {"usd": 0.01, "input_tokens": 3, "output_tokens": 4},
        },
        {
            "event_type": "tool_call",
            "summary": "pytest",
            "run_id": "run-observatory-1",
            "graph_id": "engineering-loop",
            "payload": {"status": "passed"},
            "case_id": "case_123",
            "change_id": "AS215932/agent-core#10",
        },
        {
            "event_type": "knowledge_context_pack",
            "summary": "context pack",
            "run_id": "run-knowledge-1",
            "graph_id": "knowledge",
        },
    ]
    with TestClient(_app(tmp_path)) as client:
        assert client.post("/v1/trace/batch", json=events).json() == {"stored": 3}

        loops = client.get("/v1/loops").json()
        assert {loop["loop_id"] for loop in loops} == {"engineering-loop", "knowledge"}

        runs = client.get("/v1/runs").json()
        assert {run["run_id"] for run in runs} == {"run-observatory-1", "run-knowledge-1"}

        detail = client.get("/v1/runs/run-observatory-1").json()
        assert detail["event_count"] == 2
        assert detail["case_ids"] == ["case_123"]
        assert detail["change_ids"] == ["AS215932/agent-core#10"]
        assert detail["cost_usd"] == 0.01

        timeline = client.get("/v1/runs/run-observatory-1/events").json()
        assert [item["title"] for item in timeline] == ["model_call", "tool_call"]
        assert timeline[0]["links"][0]["kind"] == "github_pr"

        actions = client.get("/v1/actions", params={"case_id": "case_123"}).json()
        assert len(actions) == 2
        assert {item["case_id"] for item in actions} == {"case_123"}

        topology = client.get("/v1/topology").json()
        assert "agent-core-collector" in {node["node_id"] for node in topology["nodes"]}
        assert {edge["kind"] for edge in topology["edges"]} == {"emits_trace"}

        metrics = client.get("/v1/metrics/daily").json()
        assert metrics[0]["event_count"] == 3
        assert metrics[0]["run_count"] == 2
        assert metrics[0]["graph_counts"]["engineering-loop"] == 2
