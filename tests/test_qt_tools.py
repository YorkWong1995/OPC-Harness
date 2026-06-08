from pathlib import Path

from opc.tools.qt_tools import check_qt_environment, format_qt_environment_report


def test_qt_environment_reports_missing_required_dependencies() -> None:
    results = check_qt_environment(
        env={},
        command_resolver=lambda _command: None,
        command_runner=lambda _command: (1, "missing"),
        common_qt_roots=(),
    )

    by_id = {result.id: result for result in results}
    assert by_id["cmake"].status == "missing"
    assert by_id["qt5"].status == "missing"
    assert by_id["compiler"].status == "missing"
    assert by_id["qt6"].status == "skipped"
    assert "plugins.enabled" in " ".join(by_id["qt5"].next_steps)


def test_qt_environment_detects_qt5_msvc_toolchain(tmp_path: Path) -> None:
    qt_root = tmp_path / "Qt" / "5.14.2" / "msvc2017_64"
    qt_config = qt_root / "lib" / "cmake" / "Qt5" / "Qt5Config.cmake"
    qt_config.parent.mkdir(parents=True)
    qt_config.write_text("# Qt5", encoding="utf-8")

    results = check_qt_environment(
        env={"Qt5_DIR": str(qt_config.parent)},
        command_resolver=lambda command: {"cmake": "C:/Tools/cmake.exe", "cl": "C:/BuildTools/cl.exe"}.get(command),
        command_runner=lambda _command: (0, "cmake version 3.27.0"),
        common_qt_roots=(),
    )

    by_id = {result.id: result for result in results}
    assert by_id["cmake"].status == "ok"
    assert by_id["qt5"].status == "ok"
    assert by_id["compiler"].status == "ok"
    assert by_id["cmake-generator"].status == "ok"
    assert by_id["qt-path-consistency"].status == "ok"
    assert by_id["qt5"].detected_path == str(qt_config.resolve())


def test_qt_environment_warns_when_only_qt6_is_found(tmp_path: Path) -> None:
    qt_root = tmp_path / "Qt" / "6.6.0" / "msvc2019_64"
    qt_config = qt_root / "lib" / "cmake" / "Qt6" / "Qt6Config.cmake"
    qt_config.parent.mkdir(parents=True)
    qt_config.write_text("# Qt6", encoding="utf-8")

    results = check_qt_environment(
        env={"Qt6_DIR": str(qt_config.parent)},
        command_resolver=lambda command: {"cmake": "cmake", "cl": "cl"}.get(command),
        command_runner=lambda _command: (0, "cmake version 3.27.0"),
        common_qt_roots=(),
    )

    by_id = {result.id: result for result in results}
    assert by_id["qt5"].status == "missing"
    assert "Qt6" in " ".join(by_id["qt5"].next_steps)
    assert by_id["qt6"].status == "warning"
    assert by_id["qt6"].required is False


def test_qt_environment_warns_on_qt_compiler_family_mismatch(tmp_path: Path) -> None:
    qt_root = tmp_path / "Qt" / "5.14.2" / "mingw73_64"
    qt_config = qt_root / "lib" / "cmake" / "Qt5" / "Qt5Config.cmake"
    qt_config.parent.mkdir(parents=True)
    qt_config.write_text("# Qt5", encoding="utf-8")

    results = check_qt_environment(
        env={"CMAKE_PREFIX_PATH": str(qt_root)},
        command_resolver=lambda command: {"cmake": "cmake", "cl": "cl"}.get(command),
        command_runner=lambda _command: (0, "cmake version 3.27.0"),
        common_qt_roots=(),
    )

    by_id = {result.id: result for result in results}
    assert by_id["qt-path-consistency"].status == "warning"
    assert "mingw" in by_id["qt-path-consistency"].message
    assert "msvc" in by_id["qt-path-consistency"].message


def test_qt_environment_report_is_readable() -> None:
    results = check_qt_environment(
        env={},
        command_resolver=lambda _command: None,
        command_runner=lambda _command: (1, "missing"),
        common_qt_roots=(),
    )

    report = format_qt_environment_report(results)

    assert "[missing] cmake" in report
    assert "[missing] qt5" in report
    assert "核心 OPC 能力不受影响" in report
