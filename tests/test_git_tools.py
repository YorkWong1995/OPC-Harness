"""测试 Git 只读工具。"""

import subprocess
from pathlib import Path

from opc.agent import Agent, TOOLS_READ_ONLY


def run_git(workspace: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=workspace, check=True, capture_output=True, text=True)


def test_git_status_diff_and_log_tools(tmp_path: Path):
    run_git(tmp_path, "init")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    run_git(tmp_path, "config", "user.name", "Test User")

    sample = tmp_path / "sample.txt"
    sample.write_text("one\n", encoding="utf-8")
    run_git(tmp_path, "add", "sample.txt")
    run_git(tmp_path, "commit", "-m", "initial")
    sample.write_text("one\ntwo\n", encoding="utf-8")

    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_ONLY, project_dir=tmp_path)

    assert "sample.txt" in agent._tool_git_status()
    assert "+two" in agent._tool_git_diff(path="sample.txt")
    assert "initial" in agent._tool_git_log(limit=1)


def test_read_only_tool_set_includes_git_tools():
    names = {tool["name"] for tool in TOOLS_READ_ONLY}

    assert {"git_status", "git_diff", "git_log"} <= names
