from pathlib import Path


def test_workflow_pack_baseline_specs_are_documented():
    root = Path(__file__).resolve().parent.parent
    workflow = (root / "docs" / "plan" / "workflow.md").read_text(encoding="utf-8")
    standards = (root / "docs" / "claude" / "standards.md").read_text(encoding="utf-8")

    for pack in ["bugfix", "review", "docs-update"]:
        assert f"`{pack}`" in workflow
    for field in ["id", "kind", "owner_roles", "inputs", "outputs", "permissions", "acceptance", "trace"]:
        assert f"`{field}`" in workflow
    assert "Workflow Pack 应至少包含" in standards
