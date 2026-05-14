"""测试 Agent 工具：edit_file、grep、run_command"""

import shutil
from pathlib import Path

import pytest

from opc.agent import Agent, TOOLS_READ_WRITE


@pytest.fixture
def workspace(tmp_path):
    """创建临时工作区并写入示例文件"""
    example = tmp_path / "example.py"
    example.write_text("""def hello(name):
    print(f"Hello, {name}!")

def goodbye(name):
    print(f"Goodbye, {name}!")

# TODO: Add more functions
""")
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture
def agent(workspace):
    """创建带读写工具的测试 Agent"""
    return Agent(
        role="test",
        system_prompt="你是一个测试 Agent",
        tools=TOOLS_READ_WRITE,
        project_dir=workspace,
    )


def test_edit_file_diff(agent, workspace):
    """edit_file 以 diff 模式修改文件内容"""
    result = agent._tool_edit_file(
        path="example.py",
        old_string="def hello(name):",
        new_string="def hello(name: str) -> None:",
    )
    assert "def hello(name: str) -> None:" in (workspace / "example.py").read_text()


def test_grep_basic(agent):
    """grep 搜索文件内容"""
    result = agent._tool_grep(pattern="TODO", file_glob="**/*.py")
    assert "TODO" in result


def test_grep_regex(agent):
    """grep 支持正则表达式搜索"""
    result = agent._tool_grep(pattern=r"def \w+\(", file_glob="**/*.py")
    assert "def hello" in result or "def goodbye" in result


def test_run_command_interactive_detection(agent):
    """run_command 检测交互式命令并拒绝执行"""
    result = agent._tool_run_command("npm create vite@latest")
    assert "交互式输入" in result or "非交互式标志" in result


def test_run_command_normal(agent):
    """run_command 正常执行非交互式命令"""
    result = agent._tool_run_command("python --version")
    assert "Python" in result or "exit code" in result


def test_edit_file_replace_all(agent, workspace):
    """edit_file 的 replace_all 批量替换"""
    result = agent._tool_edit_file(
        path="example.py",
        old_string='print(f"',
        new_string='print(f"[LOG] ',
        replace_all=True,
    )
    assert "替换了 2 处" in result
    content = (workspace / "example.py").read_text()
    assert "[LOG] Hello" in content and "[LOG] Goodbye" in content
