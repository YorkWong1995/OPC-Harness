"""Path validation helpers for agent tools."""

from __future__ import annotations

from pathlib import Path


def resolve_safe_path(base: Path | None, path: str) -> Path:
    root = base or Path.cwd()
    target = (root / path).resolve()
    root_resolved = root.resolve()
    try:
        if not target.is_relative_to(root_resolved):
            raise ValueError(f"路径穿越：{path} 不在项目目录内")
    except AttributeError:
        try:
            target.relative_to(root_resolved)
        except ValueError:
            raise ValueError(f"路径穿越：{path} 不在项目目录内")
    return target


def check_workspace_boundary(project_dir: Path | None, args: list[str]) -> str | None:
    if not project_dir:
        return None
    workspace = project_dir.resolve()
    for arg in args:
        if arg.startswith("-"):
            continue
        candidate = Path(arg)
        if candidate.is_absolute():
            try:
                resolved = candidate.resolve()
                if not resolved.is_relative_to(workspace):
                    return f"错误：命令参数引用了 workspace 外的路径: {arg}"
            except (OSError, ValueError):
                pass
    return None
