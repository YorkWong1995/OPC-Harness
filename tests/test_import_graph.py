"""测试 import graph 分析"""

from pathlib import Path

from opc.knowledge.import_graph import ImportGraph


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


def test_cpp_include_dependency_queries(tmp_path):
    """测试 C/C++ #include 依赖能解析到项目内头文件。"""
    src = tmp_path / "src"
    src.mkdir()
    main = src / "main.cpp"
    header = src / "feature.hpp"
    main.write_text('#include "feature.hpp"\nint main() { return 0; }\n', encoding="utf-8")
    header.write_text("int feature();\n", encoding="utf-8")

    graph = ImportGraph()
    graph.index_directory(tmp_path)

    assert graph.dependencies_of(str(main)) == ["feature.hpp"]
    assert graph.file_dependencies_of(str(main)) == [str(header.resolve())]
    assert graph.file_dependents_of(str(header.resolve())) == [str(main)]
    assert graph.impact_analysis(str(header.resolve())) == [str(main)]


def test_cpp_include_uses_compile_commands_include_dirs(tmp_path):
    """测试 compile_commands.json 中的 -I 路径用于解析尖括号 include。"""
    include_dir = tmp_path / "include"
    src_dir = tmp_path / "src"
    include_dir.mkdir()
    src_dir.mkdir()
    main = src_dir / "main.cpp"
    header = include_dir / "lib.hpp"
    main.write_text("#include <lib.hpp>\n", encoding="utf-8")
    header.write_text("int lib();\n", encoding="utf-8")
    (tmp_path / "compile_commands.json").write_text(
        '[{"directory": "' + str(tmp_path).replace("\\", "\\\\") + '", "command": "c++ -I include src/main.cpp"}]',
        encoding="utf-8",
    )

    graph = ImportGraph()
    graph.index_directory(tmp_path)

    assert graph.file_dependencies_of(str(main)) == [str(header.resolve())]


def test_cpp_unresolved_system_include_keeps_module_dependency(tmp_path):
    """未解析到项目内文件的系统 include 仍保留模块级依赖。"""
    main = tmp_path / "main.cpp"
    main.write_text("#include <vector>\n", encoding="utf-8")

    graph = ImportGraph()
    graph.index_directory(tmp_path)

    assert graph.dependencies_of(str(main)) == ["vector"]
    assert graph.file_dependencies_of(str(main)) == []


def test_syntax_error_skipped(tmp_path):
    """语法错误文件不崩溃"""
    bad = tmp_path / "bad.py"
    bad.write_text("import (\n", encoding="utf-8")

    graph = ImportGraph()
    edges = graph.index_file(bad)
    assert edges == []
