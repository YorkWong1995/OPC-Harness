"""测试索引元数据中的文件依赖。"""

from opc.knowledge.indexer import Indexer


def test_indexer_records_python_to_native_extension_dependency(tmp_path):
    project = tmp_path / "project"
    index_root = tmp_path / "index"
    project.mkdir()
    (project / "app.py").write_text("import native_ext\n", encoding="utf-8")
    (project / "native.cpp").write_text("PYBIND11_MODULE(native_ext, m) {}\n", encoding="utf-8")

    indexer = Indexer("test", index_root)
    dependencies = indexer._build_file_dependencies([(project / "app.py", project), (project / "native.cpp", project)])

    assert dependencies["app.py"] == {"dependencies": ["native.cpp"], "dependents": []}
    assert dependencies["native.cpp"] == {"dependencies": [], "dependents": ["app.py"]}
