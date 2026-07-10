from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from agent_core.collector.app import create_app
from agent_core.collector.db import TraceEventRow, init_models, make_engine, make_sessionmaker
from agent_core.contracts._base import utcnow


def _app(tmp_path):
    return create_app(f"sqlite+aiosqlite:///{tmp_path}/collector.db")


def _decision_record(insight_id: str, loop: str = "noc", action: str = "notify") -> dict[str, Any]:
    return {
        "insight_id": insight_id,
        "loop": loop,
        "fingerprint": f"fp_{insight_id}",
        "sampling_class": "surfaced",
        "candidate_type": "hotspot",
        "candidate_source": "proactive_scanner",
        "action_selected": action,
    }


def _envelope_event(
    insight_id: str, loop: str = "noc", *, with_record: bool = True
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "loop_decision_envelope": {
            "envelope_id": f"ldec_{insight_id}",
            "loop": loop,
            "input_event": {},
            "decision": "notify",
        }
    }
    if with_record:
        payload["insight_decision_record"] = _decision_record(insight_id, loop=loop)
    return {
        "event_type": "loop_decision_envelope",
        "summary": f"decision {insight_id}",
        "run_id": "cycle-1",
        "payload": payload,
    }


def _label_event(label_id: str, insight_id: str, loop: str = "noc") -> dict[str, Any]:
    return {
        "event_type": "insight_label",
        "summary": f"label {label_id}",
        "payload": {
            "insight_label": {
                "label_id": label_id,
                "insight_id": insight_id,
                "loop": loop,
                "reference_action": "notify",
                "reviewer": "svag",
            }
        },
    }


def test_insights_endpoint_returns_decisions_and_labels(tmp_path) -> None:
    with TestClient(_app(tmp_path)) as client:
        assert client.post("/v1/trace", json=_envelope_event("ins_noc_1")).status_code == 200
        assert (
            client.post("/v1/trace", json=_envelope_event("ins_soc_1", loop="soc")).status_code
            == 200
        )
        assert client.post("/v1/trace", json=_label_event("lbl_1", "ins_noc_1")).status_code == 200
        # envelope without the full record is skipped, not surfaced half-empty
        assert (
            client.post(
                "/v1/trace", json=_envelope_event("ins_bare", with_record=False)
            ).status_code
            == 200
        )

        items = client.get("/v1/insights").json()
        assert [item["record_type"] for item in items] == ["label", "decision", "decision"]
        assert items[0]["record"]["label_id"] == "lbl_1"
        assert {item["loop"] for item in items} == {"noc", "soc"}

        noc_only = client.get("/v1/insights", params={"loop": "noc"}).json()
        assert {item["loop"] for item in noc_only} == {"noc"}
        assert len(noc_only) == 2

        decisions = client.get("/v1/insights", params={"record_type": "decision"}).json()
        assert [item["record"]["insight_id"] for item in decisions] == ["ins_soc_1", "ins_noc_1"]

        future = (utcnow() + timedelta(hours=1)).isoformat()
        assert client.get("/v1/insights", params={"since": future}).json() == []
        assert client.get("/v1/insights", params={"since": "not-a-date"}).status_code == 422


def test_ingest_token_enforced_when_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HYRULE_COLLECTOR_INGEST_TOKEN", "sekrit")
    with TestClient(_app(tmp_path)) as client:
        event = _envelope_event("ins_noc_1")
        assert client.post("/v1/trace", json=event).status_code == 401
        assert (
            client.post(
                "/v1/trace", json=event, headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/v1/trace", json=event, headers={"Authorization": "Bearer sekrit"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/trace/batch", json=[event], headers={"Authorization": "Bearer sekrit"}
            ).status_code
            == 200
        )
        # reads stay open
        assert client.get("/v1/insights").status_code == 200


def test_ingest_token_not_required_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HYRULE_COLLECTOR_INGEST_TOKEN", raising=False)
    with TestClient(_app(tmp_path)) as client:
        assert client.post("/v1/trace", json=_envelope_event("ins_noc_1")).status_code == 200


def test_startup_prunes_old_insight_rows_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HYRULE_COLLECTOR_INSIGHT_RETENTION_DAYS", "180")
    url = f"sqlite+aiosqlite:///{tmp_path}/collector.db"

    async def _seed() -> None:
        engine = make_engine(url)
        await init_models(engine)
        sessionmaker = make_sessionmaker(engine)
        old = utcnow() - timedelta(days=400)
        async with sessionmaker() as session:
            session.add_all(
                [
                    TraceEventRow(
                        event_id="ev_old_insight",
                        event_type="loop_decision_envelope",
                        summary="old insight",
                        received_at=old,
                        event={"payload": {"insight_decision_record": _decision_record("ins_old")}},
                    ),
                    TraceEventRow(
                        event_id="ev_old_other",
                        event_type="model_call",
                        summary="old non-insight",
                        received_at=old,
                        event={"summary": "old non-insight"},
                    ),
                ]
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_seed())

    with TestClient(create_app(url)) as client:
        assert client.post("/v1/trace", json=_envelope_event("ins_new")).status_code == 200
        insight_ids = [
            item["record"]["insight_id"]
            for item in client.get("/v1/insights", params={"record_type": "decision"}).json()
        ]
        assert insight_ids == ["ins_new"]
        # non-insight rows are untouched by the insight retention prune
        summaries = [
            event.get("summary") for event in client.get("/v1/trace", params={"limit": 50}).json()
        ]
        assert "old non-insight" in summaries


def test_retention_zero_disables_prune(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HYRULE_COLLECTOR_INSIGHT_RETENTION_DAYS", "0")
    url = f"sqlite+aiosqlite:///{tmp_path}/collector.db"

    async def _seed() -> None:
        engine = make_engine(url)
        await init_models(engine)
        sessionmaker = make_sessionmaker(engine)
        async with sessionmaker() as session:
            session.add(
                TraceEventRow(
                    event_id="ev_old_insight",
                    event_type="loop_decision_envelope",
                    summary="old insight",
                    received_at=utcnow() - timedelta(days=4000),
                    event={"payload": {"insight_decision_record": _decision_record("ins_ancient")}},
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_seed())

    with TestClient(create_app(url)) as client:
        items = client.get("/v1/insights").json()
        assert [item["record"]["insight_id"] for item in items] == ["ins_ancient"]
