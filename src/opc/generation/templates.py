"""Filesystem template rendering for project generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_PROJECT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_CPP_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class TemplateRenderError(ValueError):
    pass


@dataclass(frozen=True)
class TemplateRenderResult:
    planned_files: tuple[Path, ...]
    written_files: tuple[Path, ...]


def build_project_template_variables(
    project_name: str,
    *,
    class_name: str = "MainWindow",
    qt_major_version: str = "5",
) -> dict[str, str]:
    if not _PROJECT_NAME_RE.fullmatch(project_name):
        raise TemplateRenderError(f"invalid project_name: {project_name}")
    if not _CPP_IDENTIFIER_RE.fullmatch(class_name):
        raise TemplateRenderError(f"invalid class_name: {class_name}")
    if not qt_major_version.isdigit():
        raise TemplateRenderError(f"invalid qt_major_version: {qt_major_version}")
    executable_name = re.sub(r"[^A-Za-z0-9_]", "_", project_name)
    return {
        "project_name": project_name,
        "executable_name": executable_name,
        "class_name": class_name,
        "qt_major_version": qt_major_version,
    }


def render_template_directory(
    template_root: Path,
    target_dir: Path,
    variables: dict[str, str],
    *,
    file_patterns: tuple[str, ...] | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> TemplateRenderResult:
    template_root = template_root.resolve()
    target_root = target_dir.resolve()
    if not template_root.is_dir():
        raise TemplateRenderError(f"template root not found: {template_root}")

    entries = _collect_template_files(template_root, file_patterns)
    planned: list[Path] = []
    rendered: list[tuple[Path, str]] = []
    for source in entries:
        source_resolved = source.resolve()
        if not _is_relative_to(source_resolved, template_root):
            raise TemplateRenderError(f"template file escapes template root: {source}")
        relative_path = source.relative_to(template_root)
        _validate_relative_path(relative_path)
        target = (target_root / relative_path).resolve()
        if not _is_relative_to(target, target_root):
            raise TemplateRenderError(f"target path escapes target directory: {relative_path}")
        if target.exists() and not overwrite:
            raise TemplateRenderError(f"target file already exists: {target}")
        planned.append(target)
        rendered.append((target, _render_text(source.read_text(encoding="utf-8"), variables)))

    if dry_run:
        return TemplateRenderResult(planned_files=tuple(planned), written_files=())

    for target, content in rendered:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return TemplateRenderResult(planned_files=tuple(planned), written_files=tuple(planned))


def _collect_template_files(template_root: Path, file_patterns: tuple[str, ...] | None) -> tuple[Path, ...]:
    if file_patterns is None:
        return tuple(sorted(path for path in template_root.rglob("*") if path.is_file()))

    files: dict[Path, None] = {}
    for pattern in file_patterns:
        _validate_pattern(pattern)
        matches = sorted(path for path in template_root.glob(pattern) if path.is_file())
        if not matches:
            raise TemplateRenderError(f"template pattern matched no files: {pattern}")
        for match in matches:
            files[match] = None
    return tuple(files)


def _render_text(text: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise TemplateRenderError(f"unknown template variable: {name}")
        return variables[name]

    rendered = _PLACEHOLDER_RE.sub(replace, text)
    if "{{" in rendered or "}}" in rendered:
        raise TemplateRenderError("unresolved template placeholder")
    return rendered


def _validate_pattern(pattern: str) -> None:
    path = Path(pattern)
    if path.is_absolute() or ".." in path.parts:
        raise TemplateRenderError(f"unsafe template file pattern: {pattern}")


def _validate_relative_path(path: Path) -> None:
    if path.is_absolute() or ".." in path.parts:
        raise TemplateRenderError(f"unsafe template relative path: {path}")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
