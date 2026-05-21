from pathlib import Path

from opc.workflow import ROLE_CONTEXT_SECTIONS


def test_l1_l6_matrix_and_context_contract_are_documented():
    root = Path(__file__).resolve().parent.parent
    architecture = (root / "docs" / "plan" / "architecture.md").read_text(encoding="utf-8")
    rag_doc = (root / "docs" / "knowledge-retrieval-design.md").read_text(encoding="utf-8")

    for layer in ["L1", "L2", "L3", "L4", "L5", "L6"]:
        assert layer in architecture
    assert "ROLE_CONTEXT_SECTIONS" in architecture
    assert "context_sources" in architecture
    assert "当前文件事实优先" in architecture
    assert "RAG 来源标注" in rag_doc


def test_role_context_allowlist_contains_source_attribution():
    assert ROLE_CONTEXT_SECTIONS
    for role, sections in ROLE_CONTEXT_SECTIONS.items():
        assert "context_sources" in sections, role
        assert "task_goal" in sections, role
