"""测试 import graph 分析"""

from pathlib import Path

from src.opc.knowledge.import_graph import ImportGraph


def test_index_imports(tmp_path):
    """测试提取 import 语句"""
    code = '''
import os
import json
from pathlib import Path
from .utils import helper_func
'''
    py_file = tmp_path / "main.py"
    py_file.write_text(code, encoding="utf-8")

    graph = ImportGraph()
    edges = graph.index_file(py_file)

    targets = [e.target for e in edges]
    assert "os" in targets
    assert "json" in targets
    assert "pathlib" in targets
    assert ".utils" in targets


def test_dependents_of(tmp_path):
    """测试查找依赖某模块的文件"""
    (tmp_path / "a.py").write_text("from utils import foo\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import utils\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("import os\n", encoding="utf-8")

    graph = ImportGraph()
    graph.index_directory(tmp_path)

    deps = graph.dependents_of("utils")
    assert str(tmp_path / "a.py") in deps
    assert str(tmp_path / "b.py") in deps
    assert str(tmp_path / "c.py") not in deps


def test_dependencies_of(tmp_path):
    """测试查找文件的依赖"""
    code = '''
import os
from pathlib import Path
from .config import Settings
'''
    py_file = tmp_path / "app.py"
    py_file.write_text(code, encoding="utf-8")

    graph = ImportGraph()
    graph.index_file(py_file)

    deps = graph.dependencies_of(str(py_file))
    assert "os" in deps
    assert "pathlib" in deps
    assert ".config" in deps


def test_file_dependency_queries(tmp_path):
    """测试按文件查询项目内直接依赖和被依赖文件"""
    (tmp_path / "app.py").write_text("from .config import Settings\nimport utils\n", encoding="utf-8")
    (tmp_path / "config.py").write_text("class Settings: pass\n", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")

    graph = ImportGraph()
    graph.index_directory(tmp_path)

    app = str(tmp_path / "app.py")
    config = str(tmp_path / "config.py")
    utils = str(tmp_path / "utils.py")

    assert graph.file_dependencies_of(app) == [config, utils]
    assert graph.file_dependents_of(config) == [app]
    assert graph.file_dependents_of(utils) == [app]


def test_syntax_error_skipped(tmp_path):
    """语法错误文件不崩溃"""
    bad = tmp_path / "bad.py"
    bad.write_text("import (\n", encoding="utf-8")

    graph = ImportGraph()
    edges = graph.index_file(bad)
    assert edges == []
