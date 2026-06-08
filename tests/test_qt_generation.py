import os
import subprocess
from pathlib import Path

import pytest

from opc.agent import Agent, TOOLS_READ_WRITE
from opc.generation.templates import build_project_template_variables, render_template_directory
from opc.tools.qt_tools import check_qt_environment, format_qt_environment_report

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates" / "qt" / "widgets-cmake"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "qt"


def test_qt_generation_structure_matches_expected_file_list(tmp_path: Path) -> None:
    target_dir = tmp_path / "DemoQtApp"
    expected_files = tuple(
        line.strip()
        for line in (FIXTURE_ROOT / "expected_widgets_cmake_files.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )

    result = render_template_directory(
        TEMPLATE_ROOT,
        target_dir,
        build_project_template_variables("DemoQtApp"),
    )

    written_files = tuple(sorted(path.relative_to(target_dir).as_posix() for path in result.written_files))
    assert written_files == tuple(sorted(expected_files))
    assert "find_package(Qt5 5.14 REQUIRED COMPONENTS Widgets)" in (target_dir / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "QApplication" in (target_dir / "src" / "main.cpp").read_text(encoding="utf-8")
    assert "{{" not in (target_dir / "src" / "MainWindow.cpp").read_text(encoding="utf-8")


def test_qt_generation_is_detected_as_cmake_project(tmp_path: Path) -> None:
    target_dir = tmp_path / "DemoQtApp"
    render_template_directory(
        TEMPLATE_ROOT,
        target_dir,
        build_project_template_variables("DemoQtApp"),
    )
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=target_dir)

    assert agent._detect_build_commands() == [["cmake", "-S", ".", "-B", "build"], ["cmake", "--build", "build"]]


def test_qt_generation_real_build_when_environment_is_available(tmp_path: Path) -> None:
    environment_results = check_qt_environment()
    missing_required = [result for result in environment_results if result.required and result.status != "ok"]
    if missing_required:
        pytest.skip("Qt 5.14.2/CMake/compiler environment unavailable:\n" + format_qt_environment_report(environment_results))

    target_dir = tmp_path / "DemoQtApp"
    build_dir = target_dir / "build"
    render_template_directory(
        TEMPLATE_ROOT,
        target_dir,
        build_project_template_variables("DemoQtApp"),
    )
    qt5 = next(result for result in environment_results if result.id == "qt5")
    env = dict(os.environ)
    if qt5.detected_path:
        env.setdefault("Qt5_DIR", str(Path(qt5.detected_path).parent))

    configure = subprocess.run(
        ["cmake", "-S", str(target_dir), "-B", str(build_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )
    assert configure.returncode == 0, configure.stdout + configure.stderr

    build = subprocess.run(
        ["cmake", "--build", str(build_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )
    assert build.returncode == 0, build.stdout + build.stderr
