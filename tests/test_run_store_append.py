"""测试 P2.2 RunStore append 优化：append 不再每次重写 trace。"""

import json

from opc.run_store import RunStore


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


def test_load_falls_back_to_trace_when_no_jsonl(tmp_path):
    """老格式（仅有 run_trace.json）仍可加载。"""
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
