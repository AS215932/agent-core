from __future__ import annotations

import json

from agent_core.contracts.tracing import TraceEvent
from agent_core.tracing import (
    HttpSink,
    JsonlFileSink,
    MultiSink,
    NullSink,
    sink_from_env,
)


def _event() -> TraceEvent:
    return TraceEvent(event_type="model_call", summary="x", run_id="r1")


def test_null_sink() -> None:
    assert NullSink().emit(_event()) is False


def test_jsonl_file_sink(tmp_path) -> None:
    sink = JsonlFileSink(tmp_path / "t.jsonl")
    assert sink.emit(_event()) is True
    lines = (tmp_path / "t.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event_type"] == "model_call"


def test_http_sink_success(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def getcode(self):
            return 204

    def _fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["data"] = request.data
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    assert HttpSink("http://collector/v1/trace").emit(_event()) is True
    assert captured["url"] == "http://collector/v1/trace"
    assert json.loads(captured["data"])["event_type"] == "model_call"


def test_http_sink_failure(monkeypatch) -> None:
    def _boom(request, timeout=None):
        raise OSError("collector down")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert HttpSink("http://collector").emit(_event()) is False


def test_multi_sink(tmp_path) -> None:
    file_sink = JsonlFileSink(tmp_path / "m.jsonl")
    multi = MultiSink([NullSink(), file_sink])
    assert multi.emit(_event()) is True
    assert (tmp_path / "m.jsonl").exists()


def test_sink_from_env_disabled(monkeypatch) -> None:
    monkeypatch.delenv("HYRULE_X_TRACE", raising=False)
    assert isinstance(sink_from_env("HYRULE_X_TRACE"), NullSink)


def test_sink_from_env_file_and_http(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HYRULE_X_TRACE", "1")
    monkeypatch.setenv("HYRULE_X_TRACE_PATH", str(tmp_path / "e.jsonl"))
    monkeypatch.setenv("HYRULE_X_TRACE_COLLECTOR_URL", "http://collector/v1/trace")
    sink = sink_from_env("HYRULE_X_TRACE")
    assert isinstance(sink, MultiSink)
    assert len(sink.sinks) == 2
