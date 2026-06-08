"""测试 build/lint/typecheck 工具。"""

from pathlib import Path
import sys

from opc.agent import Agent, TOOLS_READ_WRITE


def test_lint_tool_detects_python_project(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    result = agent._tool_run_lint()
    assert "ruff" in result or "exit code" in result or "未安装" in result


def test_typecheck_tool_detects_python_project(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    result = agent._tool_run_typecheck()
    assert "mypy" in result or "exit code" in result or "未安装" in result


def test_build_tool_detects_python_project(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    result = agent._tool_run_build()
    assert "pip" in result or "exit code" in result or "未安装" in result or "无输出" in result


def test_build_tool_returns_error_when_no_project(tmp_path: Path):
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    result = agent._tool_run_build()
    assert "未检测到" in result


def test_build_command_detects_cmake_project(tmp_path: Path):
    (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.5)\n", encoding="utf-8")
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    assert agent._detect_build_commands() == [["cmake", "-S", ".", "-B", "build"], ["cmake", "--build", "build"]]
    assert agent._detect_build_command() == ["cmake", "-S", ".", "-B", "build"]


def test_build_command_keeps_existing_project_type_priority(tmp_path: Path):
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.5)\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert agent._detect_build_command() == [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"]

    (tmp_path / "pyproject.toml").unlink()
    (tmp_path / "package.json").write_text('{"scripts":{"build":"echo ok"}}\n', encoding="utf-8")
    assert agent._detect_build_command() == ["npm", "run", "build"]

    (tmp_path / "package.json").unlink()
    (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")
    assert agent._detect_build_command() == ["cargo", "build"]
