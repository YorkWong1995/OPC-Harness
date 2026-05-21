from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_trace_inspect_read_only_capability_is_documented():
    workflow_doc = (ROOT / "docs/plan/workflow.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for text in [workflow_doc, readme]:
        assert "opc trace inspect" in text
        assert "只读" in text
        assert "不重跑" in text

    for field in [
        "timeline",
        "artifacts",
        "tool_calls",
        "decisions",
        "failures",
        "metrics",
        "compatibility",
    ]:
        assert field in workflow_doc

    for source in [
        "run_events.jsonl",
        "run_trace.json",
        "run_metrics.json",
        ".opc_state.json",
    ]:
        assert source in workflow_doc


def test_trace_inspect_definition_includes_safe_output_modes():
    workflow_doc = (ROOT / "docs/plan/workflow.md").read_text(encoding="utf-8")

    for token in ["--json", "--focus", "failures", "decisions", "tools", "artifacts"]:
        assert token in workflow_doc
    for forbidden_action in ["不重跑", "不修复", "不审批", "不删除文件"]:
        assert forbidden_action in workflow_doc
