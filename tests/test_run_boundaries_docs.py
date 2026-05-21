from pathlib import Path


def test_thread_session_run_boundaries_are_documented():
    root = Path(__file__).resolve().parent.parent
    workflow = (root / "docs" / "plan" / "workflow.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    for term in ["Thread", "Session", "Run", "Artifact", "Checkpoint"]:
        assert term in workflow
    assert "opc resume" in workflow
    assert "不等同长期 memory" in workflow or "不等同于长期 memory" in readme
