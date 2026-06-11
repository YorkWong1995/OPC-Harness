"""C/C++ 符号搜索：通过 ctags 提取函数、类型、宏和成员定义。"""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import tempfile

from .symbol_search import Symbol


CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}


def _ctags_executable() -> str:
    """解析 ctags 可执行文件路径。

    优先使用环境变量 OPC_CTAGS_PATH（可指向 ctags.exe 或其所在目录），
    否则回退到 PATH 中的 "ctags"。
    """
    configured = os.environ.get("OPC_CTAGS_PATH", "").strip()
    if configured:
        path = Path(configured)
        if path.is_dir():
            for candidate in ("ctags.exe", "ctags"):
                exe = path / candidate
                if exe.exists():
                    return str(exe)
        return str(path)
    return "ctags"

_KIND_MAP = {
    "c": "class",
    "class": "class",
    "d": "macro",
    "macro": "macro",
    "e": "enum",
    "enum": "enum",
    "enumerator": "enum_member",
    "f": "function",
    "function": "function",
    "g": "enum_member",
    "m": "method",
    "member": "method",
    "p": "function",
    "prototype": "function",
    "s": "struct",
    "struct": "struct",
    "u": "union",
    "union": "union",
    "v": "variable",
    "variable": "variable",
}


class CppSymbolSearch:
    """基于 ctags 的 C/C++ 符号索引。"""

    def __init__(self):
        self.symbols: list[Symbol] = []

    def index_file(self, file_path: Path) -> list[Symbol]:
        if file_path.suffix.lower() not in CPP_EXTENSIONS:
            return []
        return self._run_ctags(file_path.parent, [file_path])

    def index_directory(self, directory: Path) -> int:
        source_files = [path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in CPP_EXTENSIONS]
        if not source_files:
            return 0
        return len(self._run_ctags(directory, source_files))

    def search(self, query: str, kind: str | None = None, limit: int = 20) -> list[Symbol]:
        query_lower = query.lower()
        results = []
        for symbol in self.symbols:
            if kind and symbol.kind != kind:
                continue
            if query_lower in symbol.name.lower():
                results.append(symbol)
        results.sort(key=lambda symbol: (symbol.name.lower() != query_lower, len(symbol.name), symbol.name))
        return results[:limit]

    def find_definition(self, name: str, kind: str | None = None) -> Symbol | None:
        matches = [symbol for symbol in self.symbols if symbol.name == name and (kind is None or symbol.kind == kind)]
        if matches:
            return sorted(matches, key=lambda symbol: (symbol.file_path, symbol.line))[0]
        results = self.search(name, kind=kind, limit=1)
        return results[0] if results else None

    def definitions_in_file(self, file_path: str, kind: str | None = None) -> list[Symbol]:
        return sorted(
            [symbol for symbol in self.symbols if symbol.file_path == file_path and (kind is None or symbol.kind == kind)],
            key=lambda symbol: (symbol.line, symbol.name),
        )

    def methods_of_class(self, class_name: str) -> list[Symbol]:
        return sorted(
            [symbol for symbol in self.symbols if symbol.kind == "method" and symbol.owner == class_name],
            key=lambda symbol: (symbol.file_path, symbol.line, symbol.name),
        )

    def load_tags(self, tags_path: Path, root: Path) -> list[Symbol]:
        found: list[Symbol] = []
        for line in tags_path.read_text(encoding="utf-8", errors="replace").splitlines():
            symbol = self._parse_tag_line(line, root)
            if symbol is not None:
                found.append(symbol)
        self.symbols.extend(found)
        return found

    def _run_ctags(self, root: Path, source_files: list[Path]) -> list[Symbol]:
        with tempfile.TemporaryDirectory() as temp_dir:
            tags_path = Path(temp_dir) / "tags"
            command = [
                _ctags_executable(),
                "--fields=+nK",
                "--extras=+q",
                "--kinds-C=+p",
                "--kinds-C++=+p",
                "-I", "DLLEXPORT",
                "-I", "DLLIMPORT",
                "-I", "__attribute__+",
                "-f",
                str(tags_path),
                *[str(path) for path in source_files],
            ]
            try:
                result = subprocess.run(
                    command,
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return []
            if result.returncode != 0 or not tags_path.exists():
                return []
            return self.load_tags(tags_path, root)

    @staticmethod
    def _parse_tag_line(line: str, root: Path) -> Symbol | None:
        if not line or line.startswith("!"):
            return None
        parts = line.split("\t")
        if len(parts) < 4:
            return None

        name, file_name, excmd = parts[:3]
        raw_kind = parts[3]
        fields = parts[4:]
        attrs = {}
        for field in fields:
            if ":" in field:
                key, value = field.split(":", 1)
                attrs[key] = value

        kind = _KIND_MAP.get(raw_kind, raw_kind)
        line_no = _line_number(excmd, attrs)
        file_path = Path(file_name)
        if not file_path.is_absolute():
            file_path = (root / file_path).resolve()
        owner = attrs.get("class") or attrs.get("struct") or attrs.get("union") or attrs.get("namespace") or ""
        signature = _signature(kind, name, attrs)
        return Symbol(name=name, kind=kind, file_path=str(file_path), line=line_no, signature=signature, owner=owner)


def _line_number(excmd: str, attrs: dict[str, str]) -> int:
    if attrs.get("line", "").isdigit():
        return int(attrs["line"])
    raw = excmd.removesuffix(';"')
    return int(raw) if raw.isdigit() else 0


def _signature(kind: str, name: str, attrs: dict[str, str]) -> str:
    signature = attrs.get("signature", "")
    typeref = attrs.get("typeref", "")
    if signature:
        return f"{kind} {name}{signature}"
    if typeref:
        return f"{kind} {name}: {typeref}"
    return f"{kind} {name}"
