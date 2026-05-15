"""测试文件关联功能"""

from pathlib import Path

from opc.knowledge.test_association import TestFileAssociator


def test_find_tests_by_name(tmp_path):
    """按命名约定找到测试文件"""
    # 创建源文件
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "config.py").write_text("x = 1\n", encoding="utf-8")

    # 创建测试文件
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_config.py").write_text("def test_x(): pass\n", encoding="utf-8")

    assoc = TestFileAssociator(tmp_path)
    results = assoc.find_tests_for(str(src_dir / "config.py"))

    assert str(tests_dir / "test_config.py") in results


def test_find_tests_by_import(tmp_path):
    """通过 import 关系找到测试文件"""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "workflow.py").write_text("def run(): pass\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_e2e.py").write_text(
        "from src.opc.workflow import run\n\ndef test_run(): pass\n",
        encoding="utf-8"
    )

    assoc = TestFileAssociator(tmp_path)
    results = assoc.find_tests_for(str(src_dir / "workflow.py"))

    assert str(tests_dir / "test_e2e.py") in results


def test_find_tests_by_mirrored_src_path(tmp_path):
    """根据 src 下的相对路径找到镜像测试文件"""
    src_dir = tmp_path / "src" / "opc"
    src_dir.mkdir(parents=True)
    (src_dir / "workflow.py").write_text("def run(): pass\n", encoding="utf-8")

    test_dir = tmp_path / "tests" / "opc"
    test_dir.mkdir(parents=True)
    (test_dir / "test_workflow.py").write_text("def test_run(): pass\n", encoding="utf-8")

    assoc = TestFileAssociator(tmp_path)
    results = assoc.find_tests_for(str(src_dir / "workflow.py"))

    assert str(test_dir / "test_workflow.py") in results


def test_find_tests_by_recursive_import(tmp_path):
    """递归扫描 tests 子目录中的 import 关联"""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "settings.py").write_text("VALUE = 1\n", encoding="utf-8")

    nested = tmp_path / "tests" / "unit"
    nested.mkdir(parents=True)
    (nested / "test_settings_flow.py").write_text("import settings\n", encoding="utf-8")

    assoc = TestFileAssociator(tmp_path)
    results = assoc.find_tests_for(str(src_dir / "settings.py"))

    assert str(nested / "test_settings_flow.py") in results


def test_no_tests_found(tmp_path):
    """没有关联测试时返回空列表"""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "orphan.py").write_text("x = 1\n", encoding="utf-8")

    assoc = TestFileAssociator(tmp_path)
    results = assoc.find_tests_for(str(src_dir / "orphan.py"))

    assert results == []


def test_find_by_import_does_not_falsely_match(tmp_path):
    """回归用例：旧实现 'from' in content and module_name in content 会误匹配
    任何含 from 关键字且文本中出现 module_name 的文件，比如 docstring 或注释。
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "config.py").write_text("x = 1\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    # 该测试文件含 from 关键字（import 其他模块）和 'config' 字符串（在注释中），
    # 但并未真正 import config 模块。新实现不应误匹配。
    (tests_dir / "test_other.py").write_text(
        "from os import path\n"
        "# this test reads config from disk via path.join\n"
        "def test_x(): pass\n",
        encoding="utf-8",
    )
    # 同时构造一条真实 import，验证正例仍能命中
    (tests_dir / "test_real.py").write_text(
        "import config\n\ndef test_y(): pass\n",
        encoding="utf-8",
    )

    assoc = TestFileAssociator(tmp_path)
    results = assoc.find_tests_for(str(src_dir / "config.py"))

    assert str(tests_dir / "test_real.py") in results
    assert str(tests_dir / "test_other.py") not in results
