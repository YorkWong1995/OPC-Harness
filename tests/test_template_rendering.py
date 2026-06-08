from pathlib import Path

import pytest

from opc.generation.templates import (
    TemplateRenderError,
    build_project_template_variables,
    render_template_directory,
)


TEMPLATE_ROOT = Path("templates/qt/widgets-cmake")


def test_render_qt_template_writes_complete_project(tmp_path: Path) -> None:
    variables = build_project_template_variables("DemoQtApp")
    target_dir = tmp_path / "DemoQtApp"

    result = render_template_directory(TEMPLATE_ROOT, target_dir, variables)

    expected = {
        target_dir / "CMakeLists.txt",
        target_dir / "src" / "main.cpp",
        target_dir / "src" / "MainWindow.h",
        target_dir / "src" / "MainWindow.cpp",
    }
    assert set(result.written_files) == expected
    assert set(result.planned_files) == expected
    assert "find_package(Qt5 5.14 REQUIRED COMPONENTS Widgets)" in (target_dir / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "{{" not in (target_dir / "src" / "main.cpp").read_text(encoding="utf-8")
    assert "DemoQtApp" in (target_dir / "src" / "MainWindow.cpp").read_text(encoding="utf-8")


def test_render_qt_template_rejects_invalid_project_name() -> None:
    with pytest.raises(TemplateRenderError, match="invalid project_name"):
        build_project_template_variables("../DemoQtApp")


def test_render_qt_template_rejects_existing_target_file(tmp_path: Path) -> None:
    variables = build_project_template_variables("DemoQtApp")
    target_dir = tmp_path / "DemoQtApp"
    target_dir.mkdir()
    existing = target_dir / "CMakeLists.txt"
    existing.write_text("keep me", encoding="utf-8")

    with pytest.raises(TemplateRenderError, match="target file already exists"):
        render_template_directory(TEMPLATE_ROOT, target_dir, variables)

    assert existing.read_text(encoding="utf-8") == "keep me"


def test_render_qt_template_rejects_path_traversal_pattern(tmp_path: Path) -> None:
    variables = build_project_template_variables("DemoQtApp")

    with pytest.raises(TemplateRenderError, match="unsafe template file pattern"):
        render_template_directory(
            TEMPLATE_ROOT,
            tmp_path / "DemoQtApp",
            variables,
            file_patterns=("../outside.txt",),
        )
