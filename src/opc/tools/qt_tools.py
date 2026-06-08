"""Qt environment diagnostics for optional project type plugins."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import os
import shutil
import subprocess

QtCheckStatus = Literal["ok", "missing", "warning", "skipped"]
CommandResolver = Callable[[str], str | None]
CommandRunner = Callable[[Sequence[str]], tuple[int, str]]


@dataclass(frozen=True)
class QtEnvironmentCheckResult:
    id: str
    status: QtCheckStatus
    required: bool
    detected_path: str | None
    check_command: str
    message: str
    next_steps: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "status": self.status,
            "required": self.required,
            "detected_path": self.detected_path,
            "check_command": self.check_command,
            "message": self.message,
            "next_steps": list(self.next_steps),
        }


def check_qt_environment(
    *,
    env: Mapping[str, str] | None = None,
    command_resolver: CommandResolver | None = None,
    command_runner: CommandRunner | None = None,
    common_qt_roots: Sequence[Path] | None = None,
) -> tuple[QtEnvironmentCheckResult, ...]:
    environment = env or os.environ
    resolver = command_resolver or (lambda command: shutil.which(command, path=environment.get("PATH")))
    runner = command_runner or _run_command_version
    qt5 = _find_qt_config("5", environment, common_qt_roots)
    qt6 = _find_qt_config("6", environment, common_qt_roots)
    cmake = _check_cmake(resolver, runner)
    compiler = _check_compiler(resolver)
    return (
        cmake,
        _check_qt5(qt5, qt6),
        _check_qt6(qt6),
        compiler,
        _check_cmake_generator(compiler),
        _check_qt_path_consistency(qt5, compiler),
    )


def format_qt_environment_report(results: Sequence[QtEnvironmentCheckResult]) -> str:
    lines: list[str] = []
    for result in results:
        required = "required" if result.required else "optional"
        path = f" path={result.detected_path}" if result.detected_path else ""
        lines.append(f"[{result.status}] {result.id} ({required}){path}: {result.message}")
        lines.append(f"  check: {result.check_command}")
        for step in result.next_steps:
            lines.append(f"  - {step}")
    return "\n".join(lines)


def _check_cmake(resolver: CommandResolver, runner: CommandRunner) -> QtEnvironmentCheckResult:
    cmake = resolver("cmake")
    if not cmake:
        return QtEnvironmentCheckResult(
            id="cmake",
            status="missing",
            required=True,
            detected_path=None,
            check_command="cmake --version",
            message="CMake 未在 PATH 中找到。",
            next_steps=("安装 CMake 并确认 cmake 在 PATH 中。", "重跑 cmake --version。"),
        )
    return_code, output = runner([cmake, "--version"])
    if return_code != 0:
        return QtEnvironmentCheckResult(
            id="cmake",
            status="warning",
            required=True,
            detected_path=cmake,
            check_command="cmake --version",
            message=f"CMake 可执行但版本检查失败：{output or return_code}",
            next_steps=("确认 CMake 安装完整并可从当前 shell 执行。",),
        )
    first_line = output.splitlines()[0] if output else "CMake 可执行。"
    return QtEnvironmentCheckResult(
        id="cmake",
        status="ok",
        required=True,
        detected_path=cmake,
        check_command="cmake --version",
        message=first_line,
    )


def _check_qt5(qt5: Path | None, qt6: Path | None) -> QtEnvironmentCheckResult:
    if qt5:
        return QtEnvironmentCheckResult(
            id="qt5",
            status="ok",
            required=True,
            detected_path=str(qt5),
            check_command="check Qt5_DIR or CMAKE_PREFIX_PATH for Qt5Config.cmake",
            message="已定位 Qt5Config.cmake；P9 目标环境为 Qt 5.14.2。",
        )
    next_steps = [
        "配置 Qt5_DIR=<Qt>/lib/cmake/Qt5。",
        "或配置 CMAKE_PREFIX_PATH=<Qt>，例如 C:/Qt/5.14.2/msvc2017_64。",
        "如不使用 Qt，从 plugins.enabled 移除 qt；核心 OPC 能力不受影响。",
    ]
    if qt6:
        next_steps.insert(0, "检测到 Qt6，但 P9 第一版验收目标仍是 Qt 5.14.2。")
    return QtEnvironmentCheckResult(
        id="qt5",
        status="missing",
        required=True,
        detected_path=None,
        check_command="check Qt5_DIR or CMAKE_PREFIX_PATH for Qt5Config.cmake",
        message="未定位 Qt 5.14.2 / Qt5 SDK。",
        next_steps=tuple(next_steps),
    )


def _check_qt6(qt6: Path | None) -> QtEnvironmentCheckResult:
    if qt6:
        return QtEnvironmentCheckResult(
            id="qt6",
            status="warning",
            required=False,
            detected_path=str(qt6),
            check_command="check Qt6_DIR or CMAKE_PREFIX_PATH for Qt6Config.cmake",
            message="检测到 Qt6；P9 仅将 Qt6 作为后续兼容方向。",
            next_steps=("若要通过 P9 第一版验收，请提供 Qt 5.14.2 / Qt5 SDK。",),
        )
    return QtEnvironmentCheckResult(
        id="qt6",
        status="skipped",
        required=False,
        detected_path=None,
        check_command="check Qt6_DIR or CMAKE_PREFIX_PATH for Qt6Config.cmake",
        message="未检测 Qt6；Qt6 不是 P9 第一版必需项。",
    )


def _check_compiler(resolver: CommandResolver) -> QtEnvironmentCheckResult:
    cl = resolver("cl")
    if cl:
        return QtEnvironmentCheckResult(
            id="compiler",
            status="ok",
            required=True,
            detected_path=cl,
            check_command="cl or g++ --version",
            message="已检测到 MSVC cl 编译器。",
        )
    gpp = resolver("g++")
    if gpp:
        return QtEnvironmentCheckResult(
            id="compiler",
            status="ok",
            required=True,
            detected_path=gpp,
            check_command="cl or g++ --version",
            message="已检测到 MinGW g++ 编译器。",
        )
    return QtEnvironmentCheckResult(
        id="compiler",
        status="missing",
        required=True,
        detected_path=None,
        check_command="cl or g++ --version",
        message="未检测到 MSVC cl 或 MinGW g++。",
        next_steps=(
            "MSVC 用户请从 Developer Command Prompt 启动后重试。",
            "MinGW 用户请确认 Qt kit 对应的 bin 与编译器在 PATH 中。",
        ),
    )


def _check_cmake_generator(compiler: QtEnvironmentCheckResult) -> QtEnvironmentCheckResult:
    if compiler.status != "ok" or not compiler.detected_path:
        return QtEnvironmentCheckResult(
            id="cmake-generator",
            status="warning",
            required=False,
            detected_path=None,
            check_command="cmake -G <generator>",
            message="未能基于编译器推断 CMake generator。",
            next_steps=("安装编译器后，可通过 -G 指定 Visual Studio、Ninja 或 MinGW Makefiles。",),
        )
    family = _compiler_family(compiler.detected_path)
    generator = "Visual Studio 或 Ninja" if family == "msvc" else "MinGW Makefiles 或 Ninja"
    return QtEnvironmentCheckResult(
        id="cmake-generator",
        status="ok",
        required=False,
        detected_path=None,
        check_command="cmake -G <generator>",
        message=f"可根据 {family} 编译器尝试 {generator}。",
    )


def _check_qt_path_consistency(qt5: Path | None, compiler: QtEnvironmentCheckResult) -> QtEnvironmentCheckResult:
    if not qt5 or compiler.status != "ok" or not compiler.detected_path:
        return QtEnvironmentCheckResult(
            id="qt-path-consistency",
            status="skipped",
            required=False,
            detected_path=str(qt5) if qt5 else None,
            check_command="compare Qt kit path with compiler family",
            message="缺少 Qt5 或编译器信息，跳过路径一致性检查。",
        )
    qt_family = _qt_family(qt5)
    compiler_family = _compiler_family(compiler.detected_path)
    if qt_family and qt_family != compiler_family:
        return QtEnvironmentCheckResult(
            id="qt-path-consistency",
            status="warning",
            required=False,
            detected_path=str(qt5),
            check_command="compare Qt kit path with compiler family",
            message=f"Qt kit 看起来是 {qt_family}，但编译器是 {compiler_family}。",
            next_steps=("切换匹配的 Qt kit、编译器或 CMAKE_PREFIX_PATH。",),
        )
    return QtEnvironmentCheckResult(
        id="qt-path-consistency",
        status="ok",
        required=False,
        detected_path=str(qt5),
        check_command="compare Qt kit path with compiler family",
        message="Qt kit 路径与编译器家族未发现明显冲突。",
    )


def _find_qt_config(
    major_version: str,
    env: Mapping[str, str],
    common_qt_roots: Sequence[Path] | None,
) -> Path | None:
    config_name = f"Qt{major_version}Config.cmake"
    candidate_dirs: list[Path] = []
    for variable in (f"Qt{major_version}_DIR", "Qt_DIR"):
        if value := env.get(variable):
            candidate_dirs.append(Path(value))
    if prefix := env.get("CMAKE_PREFIX_PATH"):
        candidate_dirs.extend(Path(item) for item in _split_path_list(prefix))
    candidate_dirs.extend(common_qt_roots or _default_qt_roots())
    for directory in candidate_dirs:
        found = _find_config_under(directory, config_name, major_version)
        if found:
            return found
    return None


def _find_config_under(directory: Path, config_name: str, major_version: str) -> Path | None:
    candidates = (
        directory / config_name,
        directory / "lib" / "cmake" / f"Qt{major_version}" / config_name,
        directory / "lib" / "cmake" / config_name,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _split_path_list(raw_value: str) -> tuple[str, ...]:
    separator = ";" if ";" in raw_value else os.pathsep
    return tuple(value.strip() for value in raw_value.split(separator) if value.strip())


def _default_qt_roots() -> tuple[Path, ...]:
    return (
        Path("C:/Qt/5.14.2/msvc2017_64"),
        Path("C:/Qt/5.14.2/msvc2019_64"),
        Path("C:/Qt/5.14.2/mingw73_64"),
    )


def _compiler_family(path: str) -> str:
    name = Path(path).name.lower()
    if name == "cl.exe" or name == "cl":
        return "msvc"
    return "mingw"


def _qt_family(path: Path) -> str | None:
    lowered = str(path).lower()
    if "mingw" in lowered:
        return "mingw"
    if "msvc" in lowered:
        return "msvc"
    return None


def _run_command_version(command: Sequence[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    output = result.stdout.strip()
    if result.stderr.strip():
        output = f"{output}\n{result.stderr.strip()}" if output else result.stderr.strip()
    return result.returncode, output
