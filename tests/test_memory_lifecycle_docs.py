from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_memory_lifecycle_scope_contract_is_documented():
    architecture = (ROOT / "docs/plan/architecture.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs/plan/workflow.md").read_text(encoding="utf-8")

    for scope in ["user", "project", "workflow", "run", "artifact"]:
        assert f"`{scope}`" in architecture

    for field in ["scope", "created_at", "updated_at", "expires_at", "source", "confidence", "superseded_by"]:
        assert field in architecture

    for boundary in ["Memory", "RAG", "Session", "Checkpoint", "Artifact"]:
        assert boundary in workflow

    assert "短期 run 状态默认不写入长期 memory" in workflow
    assert "当前 workspace 文件事实优先" in architecture
