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
    target_file: str | None = None


class ImportGraph:
    """基于 AST 的 Python import 依赖图"""

    def __init__(self):
        self.edges: list[ImportEdge] = []
        self._file_modules: dict[str, str] = {}
        self._module_files: dict[str, str] = {}

    def index_directory(self, directory: Path, pattern: str = "**/*.py") -> int:
        """索引目录下所有 Python 文件的 import 关系"""
        return self.index_files(list(directory.glob(pattern)), directory)

    def index_files(self, files: list[Path], root: Path) -> int:
        """索引一组 Python 文件的 import 关系"""
        py_files = [file_path for file_path in files if file_path.suffix == ".py"]
        self._register_modules(py_files, root)
        count = 0
        for py_file in py_files:
            edges = self.index_file(py_file)
            count += len(edges)
        return count

    def index_file(self, file_path: Path, root: Path | None = None) -> list[ImportEdge]:
        """解析单个文件的 import 语句"""
        if root is not None:
            self._register_modules([file_path], root)
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
                    found.append(self._edge(src, alias.name))
            elif isinstance(node, ast.ImportFrom):
                level = node.level or 0
                module = ("." * level) + (node.module or "")
                names = [alias.name for alias in node.names]
                found.append(self._edge(src, module, names))

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

    def file_dependencies_of(self, file_path: str) -> list[str]:
        """查找指定文件直接依赖的项目内文件"""
        return sorted({
            edge.target_file for edge in self.edges
            if edge.source == file_path and edge.target_file is not None
        })

    def file_dependents_of(self, file_path: str) -> list[str]:
        """查找直接依赖指定文件的项目内文件"""
        candidates = {file_path, str(Path(file_path))}
        return sorted({
            edge.source for edge in self.edges
            if edge.target_file in candidates and edge.source not in candidates
        })

    def impact_analysis(self, file_path: str) -> list[str]:
        """分析修改指定文件可能影响的其他文件（反向依赖）"""
        impacted = set(self.file_dependents_of(file_path))
        module_candidates = self._path_to_modules(file_path)
        for module in module_candidates:
            for edge in self.edges:
                if module in edge.target or any(module in n for n in edge.names):
                    if edge.source != file_path:
                        impacted.add(edge.source)
        return sorted(impacted)

    def _edge(self, source: str, target: str, names: list[str] | None = None) -> ImportEdge:
        names = names or []
        return ImportEdge(
            source=source,
            target=target,
            names=names,
            target_file=self._resolve_target_file(source, target, names),
        )

    def _register_modules(self, files: list[Path], root: Path) -> None:
        for file_path in files:
            module_name = self._module_name(file_path, root)
            file_key = str(file_path)
            self._file_modules[file_key] = module_name
            self._module_files[module_name] = file_key

    def _resolve_target_file(self, source: str, target: str, names: list[str]) -> str | None:
        module = self._absolute_module(source, target)
        candidates = [module]
        candidates.extend(f"{module}.{name}" for name in names if module)
        candidates.extend(names)
        for candidate in candidates:
            if candidate in self._module_files:
                return self._module_files[candidate]
        return None

    def _absolute_module(self, source: str, target: str) -> str:
        if not target.startswith("."):
            return target
        source_module = self._file_modules.get(source, "")
        package = source_module.rsplit(".", 1)[0] if "." in source_module else ""
        level = len(target) - len(target.lstrip("."))
        remainder = target.lstrip(".")
        parts = package.split(".") if package else []
        if level > 1:
            parts = parts[: -(level - 1)] if level - 1 <= len(parts) else []
        if remainder:
            parts.extend(remainder.split("."))
        return ".".join(part for part in parts if part)

    @staticmethod
    def _module_name(file_path: Path, root: Path) -> str:
        try:
            rel = file_path.relative_to(root)
        except ValueError:
            rel = file_path
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)

    @staticmethod
    def _path_to_modules(file_path: str) -> list[str]:
        """从文件路径推断可能的模块名"""
        p = Path(file_path)
        stem = p.stem
        parts = list(p.parts)
        modules = [stem]
        for i in range(len(parts) - 1, 0, -1):
            if parts[i].endswith(".py"):
                parts[i] = parts[i][:-3]
            candidate = ".".join(parts[i:])
            modules.append(candidate)
            if parts[i - 1] in ("src", "lib", ""):
                break
        return modules
