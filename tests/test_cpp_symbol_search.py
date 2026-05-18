"""测试 C/C++ ctags 符号搜索。"""

from pathlib import Path
import subprocess

from opc.knowledge.cpp_symbol_search import CppSymbolSearch
from opc.knowledge.symbol_search import SymbolIndex


def test_load_tags_parses_cpp_symbols(tmp_path):
    tags = tmp_path / "tags"
    source = tmp_path / "main.cpp"
    source.write_text("class Greeter {};\nint add(int a, int b) { return a + b; }\n", encoding="utf-8")
    tags.write_text(
        "!_TAG_FILE_FORMAT\t2\t/extended format/\n"
        "Greeter\tmain.cpp\t1;\"\tc\tline:1\n"
        "add\tmain.cpp\t2;\"\tf\tline:2\tsignature:(int a, int b)\n",
        encoding="utf-8",
    )

    index = CppSymbolSearch()
    symbols = index.load_tags(tags, tmp_path)

    assert [symbol.name for symbol in symbols] == ["Greeter", "add"]
    assert symbols[0].kind == "class"
    assert symbols[1].kind == "function"
    assert symbols[1].line == 2
    assert symbols[1].signature == "function add(int a, int b)"


def test_index_directory_invokes_ctags_and_searches_results(tmp_path, monkeypatch):
    source = tmp_path / "main.cpp"
    source.write_text("int add(int a, int b) { return a + b; }\n", encoding="utf-8")

    def fake_run(command, **_kwargs):
        tags_path = Path(command[command.index("-f") + 1])
        tags_path.write_text("add\tmain.cpp\t1;\"\tf\tline:1\tsignature:(int a, int b)\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    index = CppSymbolSearch()
    count = index.index_directory(tmp_path)

    assert count == 1
    definition = index.find_definition("add")
    assert definition is not None
    assert definition.file_path == str(source.resolve())


def test_python_symbol_index_includes_cpp_when_indexing_directory(tmp_path, monkeypatch):
    (tmp_path / "main.cpp").write_text("class Greeter {};\n", encoding="utf-8")
    (tmp_path / "module.py").write_text("def handle(): pass\n", encoding="utf-8")

    def fake_run(command, **_kwargs):
        tags_path = Path(command[command.index("-f") + 1])
        tags_path.write_text("Greeter\tmain.cpp\t1;\"\tc\tline:1\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    index = SymbolIndex()
    count = index.index_directory(tmp_path)

    assert count == 2
    assert index.find_definition("handle") is not None
    assert index.find_definition("Greeter", kind="class") is not None
