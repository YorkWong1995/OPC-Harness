from pathlib import Path


def test_v1_local_single_user_boundary_is_documented():
    root = Path(__file__).resolve().parent.parent
    roadmap = (root / "docs" / "plan" / "roadmap.md").read_text(encoding="utf-8")
    architecture = (root / "docs" / "plan" / "architecture.md").read_text(encoding="utf-8")

    assert "单人本地优先" in roadmap
    assert "团队协作、多用户权限、中心化控制面和托管服务不进入 v1" in roadmap
    for term in ["项目切换", "权限默认值", "审计归属", "本地 memory", "Run 冲突处理", "数据存储"]:
        assert term in roadmap
    for candidate in ["本地项目 registry", "run 冲突提示", "memory 生命周期", "数据清理/备份", "只读审计导出"]:
        assert candidate in architecture
    assert "团队治理、多用户模式和服务化部署需要单独立项" in architecture
