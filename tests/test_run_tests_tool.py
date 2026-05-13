"""测试 pytest 执行工具。"""

from pathlib import Path

from opc.agent import Agent, TOOLS_READ_WRITE


def test_run_tests_tool_executes_target(tmp_path: Path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_sample():\n    assert 1 + 1 == 2\n", encoding="utf-8")

    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    result = agent._tool_run_tests(target="test_sample.py", timeout=30)

    assert "1 passed" in result


def test_run_tests_tool_rejects_path_traversal(tmp_path: Path):
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    try:
        agent._tool_run_tests(target="../outside.py")
    except ValueError as error:
        assert "路径穿越" in str(error)
    else:
        raise AssertionError("Expected ValueError")
