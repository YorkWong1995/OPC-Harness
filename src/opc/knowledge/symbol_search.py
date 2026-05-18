"""Python 代码符号搜索：提取函数、类、方法定义并支持按名称搜索"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Symbol:
    name: str
    kind: str  # "function", "class", "method"
    file_path: str
    line: int
    signature: str
    owner: str = ""


class SymbolIndex:
    """基于 AST 的 Python 符号索引"""

    def __init__(self):
        self.symbols: list[Symbol] = []

    def index_file(self, file_path: Path) -> list[Symbol]:
        """解析单个 Python 文件，提取符号"""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return []

        found: list[Symbol] = []
        rel_path = str(file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                owner = self._find_owner_class(tree, node)
                kind = "method" if owner else "function"
                sig = self._get_function_signature(node)
                found.append(Symbol(name=node.name, kind=kind, file_path=rel_path, line=node.lineno, signature=sig, owner=owner))
            elif isinstance(node, ast.ClassDef):
                bases = ", ".join(self._get_name(b) for b in node.bases)
                sig = f"class {node.name}({bases})" if bases else f"class {node.name}"
                found.append(Symbol(name=node.name, kind="class", file_path=rel_path, line=node.lineno, signature=sig))

        self.symbols.extend(found)
        return found

    def index_directory(self, directory: Path, pattern: str | None = None) -> int:
        """索引目录下 Python 文件；默认同时通过 ctags 补充 C/C++ 符号。"""
        count = 0
        py_pattern = pattern or "**/*.py"
        for py_file in directory.glob(py_pattern):
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue
            symbols = self.index_file(py_file)
            count += len(symbols)
        if pattern is None:
            from .cpp_symbol_search import CppSymbolSearch

            cpp_symbols = CppSymbolSearch()
            count += cpp_symbols.index_directory(directory)
            self.symbols.extend(cpp_symbols.symbols)
        return count

    def search(self, query: str, kind: str | None = None, limit: int = 20) -> list[Symbol]:
        """按名称搜索符号（支持模糊匹配）"""
        query_lower = query.lower()
        results = []
        for sym in self.symbols:
            if kind and sym.kind != kind:
                continue
            if query_lower in sym.name.lower():
                results.append(sym)
        results.sort(key=lambda s: (s.name.lower() != query_lower, len(s.name), s.name))
        return results[:limit]

    def find_definition(self, name: str, kind: str | None = None) -> Symbol | None:
        """查找符号定义，优先返回精确匹配"""
        matches = [sym for sym in self.symbols if sym.name == name and (kind is None or sym.kind == kind)]
        if matches:
            return sorted(matches, key=lambda sym: (sym.file_path, sym.line))[0]
        results = self.search(name, kind=kind, limit=1)
        return results[0] if results else None

    def definitions_in_file(self, file_path: str, kind: str | None = None) -> list[Symbol]:
        """查询指定文件中的符号定义"""
        return sorted(
            [sym for sym in self.symbols if sym.file_path == file_path and (kind is None or sym.kind == kind)],
            key=lambda sym: (sym.line, sym.name),
        )

    def methods_of_class(self, class_name: str) -> list[Symbol]:
        """查询类的方法定义"""
        return sorted(
            [sym for sym in self.symbols if sym.kind == "method" and sym.owner == class_name],
            key=lambda sym: (sym.file_path, sym.line, sym.name),
        )

    def _get_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        args = []
        for arg in node.args.args:
            annotation = ""
            if arg.annotation:
                annotation = f": {self._get_name(arg.annotation)}"
            args.append(f"{arg.arg}{annotation}")
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        ret = ""
        if node.returns:
            ret = f" -> {self._get_name(node.returns)}"
        return f"{prefix} {node.name}({', '.join(args)}){ret}"

    @staticmethod
    def _find_owner_class(tree: ast.AST, target: ast.AST) -> str:
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef) and target in ast.iter_child_nodes(parent):
                return parent.name
        return ""

    @staticmethod
    def _get_name(node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{SymbolIndex._get_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Subscript):
            return f"{SymbolIndex._get_name(node.value)}[{SymbolIndex._get_name(node.slice)}]"
        return ast.dump(node)
