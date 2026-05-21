from pathlib import Path


def test_industrial_benchmark_cases_are_documented():
    root = Path(__file__).resolve().parent.parent
    benchmark = (root / "docs" / "runs" / "industrial_benchmark_cases.md").read_text(encoding="utf-8")
    success = (root / "docs" / "plan" / "success.md").read_text(encoding="utf-8")

    for case in ["bugfix", "review", "docs-update", "config-drift", "failed-tool", "rework-resume"]:
        assert case in benchmark
        assert case in success

    for required in ["固定输入", "预期产物", "验收标准", "Trace 证据", "失败判定"]:
        assert required in benchmark

    for metric in ["任务成功率", "人工介入率", "成本", "耗时", "失败可定位性"]:
        assert metric in benchmark
        assert metric in success

    assert "run_events.jsonl" in benchmark
    assert "run_trace.json" in benchmark
    assert "run_metrics.json" in benchmark
