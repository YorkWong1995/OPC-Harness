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

        for test_dir in self._find_test_dirs():
            for test_file in self._name_candidates(test_dir, source_path):
                if test_file.exists():
                    candidates.append(str(test_file))

        same_dir_test = source_path.parent / f"test_{stem}.py"
        if same_dir_test.exists() and str(same_dir_test) not in candidates:
            candidates.append(str(same_dir_test))

        candidates.extend(self._find_by_import(stem))

        return list(dict.fromkeys(candidates))  # 去重保序

    def _name_candidates(self, test_dir: Path, source_path: Path) -> list[Path]:
        stem = source_path.stem
        candidates = [
            test_dir / f"test_{stem}.py",
            test_dir / f"{stem}_test.py",
        ]
        try:
            rel = source_path.relative_to(self.project_dir)
        except ValueError:
            rel = source_path
        if rel.parts and rel.parts[0] == "src":
            rel = Path(*rel.parts[1:])
        if rel.parent != Path("."):
            candidates.extend([
                test_dir / rel.parent / f"test_{stem}.py",
                test_dir / rel.parent / f"{stem}_test.py",
            ])
        return candidates

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
            for test_file in test_dir.rglob("test_*.py"):
                try:
                    content = test_file.read_text(encoding="utf-8")
                    if f"import {module_name}" in content or f"from" in content and module_name in content:
                        if str(test_file) not in results:
                            results.append(str(test_file))
                except (UnicodeDecodeError, OSError):
                    continue
        return results
