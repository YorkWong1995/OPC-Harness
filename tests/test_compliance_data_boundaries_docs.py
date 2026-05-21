from pathlib import Path


def test_compliance_and_data_boundaries_are_documented():
    root = Path(__file__).resolve().parent.parent
    architecture = (root / "docs" / "plan" / "architecture.md").read_text(encoding="utf-8")
    rag_doc = (root / "docs" / "knowledge-retrieval-design.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    for item in ["敏感数据", "密钥/API Key", "客户代码", "日志与 trace", "外部工具出域", "Memory", "审计保留"]:
        assert item in architecture

    for boundary in ["会被读取", "会被存储", "可能出域", "保留/删除边界"]:
        assert boundary in architecture

    for term in ["凭证", "密钥", "客户代码", "context_sources", "长期 memory"]:
        assert term in rag_doc

    assert "不默认上传到 OPC 服务端" in readme
    assert "细粒度 memory 删除、审计保留期和导出策略属于 P7" in readme
