"""测试文件关联功能"""

from pathlib import Path

from src.opc.knowledge.test_association import TestFileAssociator


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
