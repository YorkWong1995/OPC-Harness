"""测试文件关联：根据源文件推荐相关测试文件"""

from __future__ import annotations

from pathlib import Path


class TestFileAssociator:
    """根据源文件路径推荐相关测试文件"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def find_tests_for(self, source_file: str) -> list[str]:
        """查找与源文件关联的测试文件"""
        source_path = Path(source_file)
        stem = source_path.stem
        candidates = []

        # 策略 1: test_<name>.py 在 tests/ 目录
        for test_dir in self._find_test_dirs():
            test_file = test_dir / f"test_{stem}.py"
            if test_file.exists():
                candidates.append(str(test_file))

        # 策略 2: <name>_test.py 在同目录或 tests/ 目录
        for test_dir in self._find_test_dirs():
            test_file = test_dir / f"{stem}_test.py"
            if test_file.exists():
                candidates.append(str(test_file))

        # 策略 3: 同目录下的 test_<name>.py
        same_dir_test = source_path.parent / f"test_{stem}.py"
        if same_dir_test.exists() and str(same_dir_test) not in candidates:
            candidates.append(str(same_dir_test))

        # 策略 4: grep 测试文件中 import 了该模块的
        candidates.extend(self._find_by_import(stem))

        return list(dict.fromkeys(candidates))  # 去重保序

    def _find_test_dirs(self) -> list[Path]:
        """查找项目中的测试目录"""
        dirs = []
        for candidate in ["tests", "test", "spec"]:
            test_dir = self.project_dir / candidate
            if test_dir.is_dir():
                dirs.append(test_dir)
        return dirs

    def _find_by_import(self, module_name: str) -> list[str]:
        """在测试文件中查找 import 了指定模块的文件"""
        results = []
        for test_dir in self._find_test_dirs():
            for test_file in test_dir.glob("test_*.py"):
                try:
                    content = test_file.read_text(encoding="utf-8")
                    if f"import {module_name}" in content or f"from" in content and module_name in content:
                        if str(test_file) not in results:
                            results.append(str(test_file))
                except (UnicodeDecodeError, OSError):
                    continue
        return results
