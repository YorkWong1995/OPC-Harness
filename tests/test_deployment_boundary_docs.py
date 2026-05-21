from pathlib import Path


def test_deployment_and_private_runtime_boundaries_are_documented():
    root = Path(__file__).resolve().parent.parent
    architecture = (root / "docs" / "plan" / "architecture.md").read_text(encoding="utf-8")
    roadmap = (root / "docs" / "plan" / "roadmap.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert 'ENTRYPOINT ["opc"]' in dockerfile
    for mode in ["本地单机 CLI", "容器化 CLI", "私有持久服务"]:
        assert mode in architecture
    for term in ["资源", "数据", "日志", "备份", "升级", "回滚"]:
        assert term in architecture
    assert "需要 server/control plane" in architecture
    assert "暂不进入近期 Roadmap" in roadmap
    assert "CLI 镜像入口" in readme
    assert "不是常驻服务、控制面或企业私有化部署方案" in readme
