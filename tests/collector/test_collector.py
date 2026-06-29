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
