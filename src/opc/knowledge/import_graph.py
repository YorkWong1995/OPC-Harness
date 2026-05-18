"""Python import graph 分析：提取模块间依赖关系"""

from __future__ import annotations

import ast
import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path


CPP_SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx"}
CPP_HEADER_EXTENSIONS = {".h", ".hh", ".hpp", ".hxx"}
CPP_EXTENSIONS = CPP_SOURCE_EXTENSIONS | CPP_HEADER_EXTENSIONS
_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]')


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
        self._include_files: dict[str, list[str]] = {}
        self._include_dirs: list[Path] = []

    def index_directory(self, directory: Path, pattern: str = "**/*.py") -> int:
        """索引目录下所有 Python 文件的 import 关系"""
        if pattern == "**/*.py":
            files = list(directory.glob(pattern))
            files.extend(path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in CPP_EXTENSIONS)
        else:
            files = list(directory.glob(pattern))
        return self.index_files(files, directory)

    def index_files(self, files: list[Path], root: Path) -> int:
        """索引一组文件的 import/include 关系"""
        py_files = [file_path for file_path in files if file_path.suffix == ".py"]
        cpp_files = [file_path for file_path in files if file_path.suffix.lower() in CPP_EXTENSIONS]
        self._register_modules(py_files, root)
        self._register_includes(cpp_files, root)
        self._include_dirs = self._load_include_dirs(root)
        count = 0
        for file_path in [*py_files, *cpp_files]:
            edges = self.index_file(file_path)
            count += len(edges)
        return count

    def index_file(self, file_path: Path, root: Path | None = None) -> list[ImportEdge]:
        """解析单个文件的 import/include 语句"""
        if file_path.suffix.lower() in CPP_EXTENSIONS:
            if root is not None:
                self._register_includes([file_path], root)
                self._include_dirs = self._load_include_dirs(root)
            return self._index_cpp_file(file_path)
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

    def _include_edge(self, source: str, include: str, quoted: bool) -> ImportEdge:
        return ImportEdge(
            source=source,
            target=include,
            target_file=self._resolve_include_file(Path(source), include, quoted),
        )

    def _index_cpp_file(self, file_path: Path) -> list[ImportEdge]:
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            return []
        found: list[ImportEdge] = []
        src = str(file_path)
        for line in lines:
            match = _INCLUDE_RE.match(line)
            if not match:
                continue
            opener, include = match.groups()
            found.append(self._include_edge(src, include, opener == '"'))
        self.edges.extend(found)
        return found

    def _register_modules(self, files: list[Path], root: Path) -> None:
        for file_path in files:
            module_name = self._module_name(file_path, root)
            file_key = str(file_path)
            self._file_modules[file_key] = module_name
            self._module_files[module_name] = file_key

    def _register_includes(self, files: list[Path], root: Path) -> None:
        self._include_files = {}
        for file_path in files:
            file_key = str(file_path)
            try:
                rel = file_path.relative_to(root).as_posix()
            except ValueError:
                rel = file_path.name
            for key in {file_path.name, rel}:
                self._include_files.setdefault(key, []).append(file_key)

    def _resolve_target_file(self, source: str, target: str, names: list[str]) -> str | None:
        module = self._absolute_module(source, target)
        candidates = [module]
        candidates.extend(f"{module}.{name}" for name in names if module)
        candidates.extend(names)
        for candidate in candidates:
            if candidate in self._module_files:
                return self._module_files[candidate]
        return None

    def _resolve_include_file(self, source: Path, include: str, quoted: bool) -> str | None:
        candidates: list[Path] = []
        if quoted:
            candidates.append(source.parent / include)
        candidates.extend(include_dir / include for include_dir in self._include_dirs)
        for candidate in candidates:
            try:
                resolved = str(candidate.resolve())
            except OSError:
                resolved = str(candidate)
            if candidate.exists():
                return resolved
        matches = self._include_files.get(include, [])
        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    def _load_include_dirs(root: Path) -> list[Path]:
        compile_commands = root / "compile_commands.json"
        dirs = [root]
        if not compile_commands.exists():
            return dirs
        try:
            entries = json.loads(compile_commands.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return dirs
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            base_dir = Path(str(entry.get("directory") or root))
            tokens = ImportGraph._compile_command_tokens(entry)
            for idx, token in enumerate(tokens):
                include_dir = None
                if token in {"-I", "/I"} and idx + 1 < len(tokens):
                    include_dir = tokens[idx + 1]
                elif token.startswith("-I") and len(token) > 2:
                    include_dir = token[2:]
                elif token.startswith("/I") and len(token) > 2:
                    include_dir = token[2:]
                if include_dir:
                    include_path = Path(include_dir)
                    dirs.append(include_path if include_path.is_absolute() else base_dir / include_path)
        return list(dict.fromkeys(dirs))

    @staticmethod
    def _compile_command_tokens(entry: dict) -> list[str]:
        arguments = entry.get("arguments")
        if isinstance(arguments, list):
            return [str(arg) for arg in arguments]
        command = entry.get("command")
        if isinstance(command, str):
            try:
                return shlex.split(command)
            except ValueError:
                return command.split()
        return []

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
