"""测试工具调用重试逻辑"""

from pathlib import Path
from unittest.mock import patch, MagicMock

from src.opc.agent import Agent


def test_tool_retry_on_transient_error(tmp_path):
    """可重试错误会触发重试"""
    agent = Agent(
        role="test",
        system_prompt="test",
        tools=[],
        project_dir=tmp_path,
        tool_max_retries=2,
    )

    call_count = 0

    def flaky_handler(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TimeoutError("connection timed out")
        return "success"

    mock_def = MagicMock()
    mock_def.handler_name = None
    mock_def.handler = flaky_handler

    with patch("src.opc.agent.get_tool", return_value=mock_def):
        result = agent._execute_tool("test_tool", {}, tool_use_id="t1")

    assert result == "success"
    assert call_count == 3


def test_tool_no_retry_on_not_found(tmp_path):
    """不可重试错误不会触发重试"""
    agent = Agent(
        role="test",
        system_prompt="test",
        tools=[],
        project_dir=tmp_path,
        tool_max_retries=2,
    )

    call_count = 0

    def not_found_handler(**kwargs):
        nonlocal call_count
        call_count += 1
        raise FileNotFoundError("文件不存在 test.txt")

    mock_def = MagicMock()
    mock_def.handler_name = None
    mock_def.handler = not_found_handler

    with patch("src.opc.agent.get_tool", return_value=mock_def):
        result = agent._execute_tool("test_tool", {}, tool_use_id="t2")

    assert "工具执行错误" in result
    assert call_count == 1


def test_tool_max_retries_exhausted(tmp_path):
    """重试次数耗尽后返回错误"""
    agent = Agent(
        role="test",
        system_prompt="test",
        tools=[],
        project_dir=tmp_path,
        tool_max_retries=1,
    )

    call_count = 0

    def always_fail(**kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("transient error")

    mock_def = MagicMock()
    mock_def.handler_name = None
    mock_def.handler = always_fail

    with patch("src.opc.agent.get_tool", return_value=mock_def):
        result = agent._execute_tool("test_tool", {}, tool_use_id="t3")

    assert "工具执行错误" in result
    assert call_count == 2  # 1 initial + 1 retry


def test_is_tool_retryable():
    """测试可重试判断逻辑"""
    assert Agent._is_tool_retryable(TimeoutError("timeout")) is True
    assert Agent._is_tool_retryable(RuntimeError("random error")) is True
    assert Agent._is_tool_retryable(FileNotFoundError("文件不存在")) is False
    assert Agent._is_tool_retryable(PermissionError("permission denied")) is False
    assert Agent._is_tool_retryable(ValueError("不允许写入")) is False
