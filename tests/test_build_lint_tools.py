"""测试 build/lint/typecheck 工具。"""

from pathlib import Path

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
