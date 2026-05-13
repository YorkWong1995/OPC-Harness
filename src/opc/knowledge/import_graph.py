"""Python import graph 分析：提取模块间依赖关系"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImportEdge:
    source: str  # 导入方文件
    target: str  # 被导入的模块/文件
    names: list[str] = field(default_factory=list)  # from X import names


class ImportGraph:
    """基于 AST 的 Python import 依赖图"""

    def __init__(self):
        self.edges: list[ImportEdge] = []
        self._file_modules: dict[str, str] = {}  # file_path -> module_name

    def index_directory(self, directory: Path, pattern: str = "**/*.py") -> int:
        """索引目录下所有 Python 文件的 import 关系"""
        count = 0
        for py_file in directory.glob(pattern):
            edges = self.index_file(py_file)
            count += len(edges)
        return count

    def index_file(self, file_path: Path) -> list[ImportEdge]:
        """解析单个文件的 import 语句"""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return []

        found: list[ImportEdge] = []
        src = str(file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.append(ImportEdge(source=src, target=alias.name))
            elif isinstance(node, ast.ImportFrom):
                level = node.level or 0
                module = ("." * level) + (node.module or "")
                names = [alias.name for alias in node.names]
                found.append(ImportEdge(source=src, target=module, names=names))

        self.edges.extend(found)
        return found

    def dependents_of(self, module_name: str) -> list[str]:
        """查找依赖指定模块的所有文件"""
        return list({
            edge.source for edge in self.edges
            if module_name in edge.target or module_name in edge.names
        })

    def dependencies_of(self, file_path: str) -> list[str]:
        """查找指定文件依赖的所有模块"""
        return list({
            edge.target for edge in self.edges
            if edge.source == file_path
        })

    def impact_analysis(self, file_path: str) -> list[str]:
        """分析修改指定文件可能影响的其他文件（反向依赖）"""
        # 从文件路径推断模块名
        module_candidates = self._path_to_modules(file_path)
        impacted = set()
        for module in module_candidates:
            for edge in self.edges:
                if module in edge.target or any(module in n for n in edge.names):
                    if edge.source != file_path:
                        impacted.add(edge.source)
        return sorted(impacted)

    @staticmethod
    def _path_to_modules(file_path: str) -> list[str]:
        """从文件路径推断可能的模块名"""
        p = Path(file_path)
        stem = p.stem
        parts = list(p.parts)
        modules = [stem]
        # 尝试构建点分模块名
        for i in range(len(parts) - 1, 0, -1):
            if parts[i].endswith(".py"):
                parts[i] = parts[i][:-3]
            candidate = ".".join(parts[i:])
            modules.append(candidate)
            if parts[i - 1] in ("src", "lib", ""):
                break
        return modules
