"""Shared helpers for resolving OPC knowledge index locations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IndexDoctorResult:
    name: str
    index_root: str
    status: str
    size_bytes: int
    checks: list[dict[str, str]]


def get_workspace_root() -> Path:
    return Path(__file__).resolve().parents[3] / "workspace"


def get_index_parent_root() -> Path:
    override = os.environ.get("OPC_INDEX_ROOT")
    if override:
        return Path(override).resolve()
    return get_workspace_root()


def get_index_root(name: str) -> Path:
    return get_index_parent_root() / name / "index"


def iter_index_roots(parent_root: Path | None = None) -> list[tuple[str, Path]]:
    root = parent_root or get_index_parent_root()
    if not root.exists():
        return []
    candidates: list[tuple[str, Path]] = []
    for child in sorted(root.iterdir()):
        index_root = child / "index"
        if index_root.is_dir():
            candidates.append((child.name, index_root))
    return candidates


def inspect_index_root(name: str, index_root: Path) -> dict[str, Any]:
    required = ["meta.json", "bm25", "vector"]
    checks: list[dict[str, str]] = []
    for item in required:
        path = index_root / item
        checks.append({"name": item, "status": "ok" if path.exists() else "missing", "detail": str(path)})

    meta_path = index_root / "meta.json"
    if meta_path.exists():
        try:
            import json

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            checks.append({"name": "meta_schema", "status": "ok" if meta.get("index_name") else "warning", "detail": f"index_name={meta.get('index_name', '')}"})
        except json.JSONDecodeError as exc:
            checks.append({"name": "meta_schema", "status": "failed", "detail": f"invalid JSON: {exc}"})

    size_bytes = sum(path.stat().st_size for path in index_root.rglob("*") if path.is_file()) if index_root.exists() else 0
    status = "failed" if any(check["status"] == "failed" for check in checks) else "warning" if any(check["status"] in {"missing", "warning"} for check in checks) else "ok"
    return asdict(IndexDoctorResult(name=name, index_root=str(index_root), status=status, size_bytes=size_bytes, checks=checks))


def inspect_indexes(name: str | None = None) -> dict[str, Any]:
    parent_root = get_index_parent_root()
    targets = [(name, get_index_root(name))] if name else iter_index_roots(parent_root)
    return {
        "index_parent_root": str(parent_root),
        "status": "missing" if not parent_root.exists() else "ok",
        "indexes": [inspect_index_root(index_name, index_root) for index_name, index_root in targets],
    }
