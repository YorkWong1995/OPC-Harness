"""测试 P2.2 RunStore append 优化：append 不再每次重写 trace。"""

import json
import os
import time

from opc.run_store import RunStore, find_run_artifacts, summarize_run, trace_summary


def test_append_writes_jsonl_not_trace(tmp_path):
    """append() 只写 events.jsonl，不再每次重写 run_trace.json。"""
    store = RunStore(tmp_path)
    store.append("foo", x=1)
    store.append("bar", y=2)

    # events.jsonl 持续增长
    events_path = tmp_path / "run_events.jsonl"
    assert events_path.exists()
    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    # trace 文件在显式 finalize 前不应存在
    assert not (tmp_path / "run_trace.json").exists()


def test_finalize_writes_trace(tmp_path):
    """finalize()/write_trace() 显式生成 run_trace.json。"""
    store = RunStore(tmp_path)
    store.append("foo", x=1)
    store.append("bar", y=2)

    path = store.write_trace(final_status="done", metrics={"k": 1})
    assert path.exists()

    trace = json.loads(path.read_text(encoding="utf-8"))
    assert trace["trace_schema_version"] == 1
    assert trace["final_status"] == "done"
    assert trace["metrics"] == {"k": 1}
    assert [e["type"] for e in trace["events"]] == ["foo", "bar"]


def test_finalize_alias(tmp_path):
    store = RunStore(tmp_path)
    store.append("foo")
    # finalize 是 write_trace 的别名，调用语义一致
    assert RunStore.finalize is RunStore.write_trace
    path = store.finalize(final_status="done")
    assert path.exists()


def test_load_prefers_jsonl_over_trace(tmp_path):
    """load 优先从 events.jsonl 重建（更新鲜），缺失才回退 trace.json。"""
    store = RunStore(tmp_path)
    store.append("a")
    store.append("b")
    # 没有 finalize；trace.json 尚未写出

    loaded = RunStore.load(tmp_path)
    assert [e.type for e in loaded.events] == ["a", "b"]
    assert loaded.run_id == store.run_id


def test_append_1000_events_under_one_second(tmp_path):
    store = RunStore(tmp_path)

    start = time.perf_counter()
    for index in range(1000):
        store.append("event", index=index)
    elapsed = time.perf_counter() - start

    assert elapsed < 1
    assert len((tmp_path / "run_events.jsonl").read_text(encoding="utf-8").splitlines()) == 1000

def test_load_falls_back_to_trace_when_no_jsonl(tmp_path):
    legacy_trace = {
        "run_id": "legacy-id",
        "final_status": "done",
        "metrics": {},
        "events": [
            {"type": "x", "payload": {"run_id": "legacy-id"}, "timestamp": "2026-01-01T00:00:00+00:00"},
        ],
    }
    (tmp_path / "run_trace.json").write_text(json.dumps(legacy_trace), encoding="utf-8")

    loaded = RunStore.load(tmp_path)
    assert loaded.run_id == "legacy-id"
    assert [e.type for e in loaded.events] == ["x"]


def test_trace_summary_reads_new_trace(tmp_path):
    store = RunStore(tmp_path)
    store.append("stage_started", stage="pm")
    store.append("tool_call", tool_name="read")
    store.write_trace(final_status="done", metrics={"totals": {"duration_seconds": 1.2}})

    summary = trace_summary(tmp_path)
    assert summary["trace_schema_version"] == 1
    assert summary["run_id"] == store.run_id
    assert summary["final_status"] == "done"
    assert summary["event_count"] == 2
    assert summary["tool_calls"] == 1
    assert summary["duration_seconds"] == 1.2


def test_trace_summary_is_compatible_with_legacy_trace(tmp_path):
    legacy_trace = {
        "run_id": "legacy-id",
        "final_status": "done",
        "metrics": {},
        "events": [
            {"type": "stage_completed", "payload": {"run_id": "legacy-id"}, "timestamp": "2026-01-01T00:00:00+00:00"},
        ],
    }
    (tmp_path / "run_trace.json").write_text(json.dumps(legacy_trace), encoding="utf-8")

    summary = trace_summary(tmp_path)
    assert summary["trace_schema_version"] == 0
    assert summary["stage_events"] == 1


def test_summarize_run_reports_failure_reason(tmp_path):
    store = RunStore(tmp_path)
    store.append("workflow_stopped", reason="max_rounds_exceeded")
    store.write_trace(final_status="已退回", metrics={"totals": {"duration_seconds": 2}})

    summary = summarize_run(tmp_path)
    assert summary.final_status == "已退回"
    assert summary.duration_seconds == 2
    assert summary.failed_reason == "max_rounds_exceeded"


def test_find_run_artifacts_returns_recent_first(tmp_path):
    older = tmp_path / "a" / "artifacts"
    newer = tmp_path / "b" / "artifacts"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "run_events.jsonl").write_text("", encoding="utf-8")
    (newer / "run_events.jsonl").write_text("", encoding="utf-8")

    os.utime(newer, (older.stat().st_mtime + 10, older.stat().st_mtime + 10))

    runs = find_run_artifacts(tmp_path)
    assert runs[0] == newer
    assert set(runs) == {older, newer}
