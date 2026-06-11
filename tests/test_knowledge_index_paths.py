"""测试 OPC 知识索引路径与 search_knowledge 行为。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from opc.cli import _get_index_root
from opc.knowledge.index_paths import get_index_root
from opc.tools.knowledge_tools import KnowledgeToolsMixin


class _DummyKnowledgeTool(KnowledgeToolsMixin):
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir


def test_shared_index_root_matches_cli(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OPC_INDEX_ROOT", str(tmp_path / "index-root"))

    cli_root = _get_index_root("demo")
    shared_root = get_index_root("demo")

    assert cli_root == shared_root
    assert cli_root == (tmp_path / "index-root" / "demo" / "index")


def test_search_knowledge_uses_cli_index_root(monkeypatch, tmp_path: Path):
    project_dir = tmp_path / "kb-project"
    project_dir.mkdir()
    (project_dir / "README.md").write_text(
        "# OPC Project KB\n\n"
        "This repository uses RAG for project knowledge.\n\n"
        "The knowledge base should find this README entry.\n",
        encoding="utf-8",
    )

    index_root = tmp_path / "custom-index-root"
    monkeypatch.setenv("OPC_INDEX_ROOT", str(index_root))
    monkeypatch.delenv("OPC_EMBEDDING_MODEL", raising=False)

    build_env = {**os.environ, "OPC_INDEX_ROOT": str(index_root)}
    build_env.pop("OPC_EMBEDDING_MODEL", None)

    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "opc.cli",
            "index",
            "--name",
            project_dir.name,
            "--dirs",
            str(project_dir),
        ],
        env=build_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    assert build.returncode == 0, f"opc index failed:\nstdout: {build.stdout}\nstderr: {build.stderr}"

    tool = _DummyKnowledgeTool(project_dir)

    mock_vs = MagicMock()
    mock_vs.query.return_value = []
    mock_vs.query_filtered.return_value = []
    with patch("opc.knowledge.vector_store.VectorStore", return_value=mock_vs):
        result = tool._tool_search_knowledge("project knowledge", top_k=3)

    assert "README.md" in result, f"Expected README.md in result, got: {result}"
    assert "RAG for project knowledge" in result or "knowledge" in result.lower(), (
        f"Expected knowledge content in result, got: {result}"
    )
    assert (index_root / project_dir.name / "index" / "meta.json").exists()
