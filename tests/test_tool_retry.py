"""测试工具调用重试逻辑"""

from pathlib import Path
from unittest.mock import patch, MagicMock

from opc.agent import Agent


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
    mock_def.timeout = 30
    mock_def.permission = "execute"
    mock_def.side_effect = "none"
    mock_def.name = "test_tool"

    with patch("opc.agent.get_tool", return_value=mock_def):
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
    mock_def.timeout = 30
    mock_def.permission = "execute"
    mock_def.side_effect = "none"
    mock_def.name = "test_tool"

    with patch("opc.agent.get_tool", return_value=mock_def):
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
    mock_def.timeout = 30
    mock_def.permission = "execute"
    mock_def.side_effect = "none"
    mock_def.name = "test_tool"

    with patch("opc.agent.get_tool", return_value=mock_def):
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


def test_max_tool_rounds_truncation(tmp_path):
    """工具循环超过 max_tool_rounds 后应中止并返回 [TRUNCATED]"""
    agent = Agent(
        role="test",
        system_prompt="test",
        tools=[{"name": "noop", "description": "noop", "input_schema": {"type": "object"}}],
        project_dir=tmp_path,
        max_tool_rounds=2,
    )

    # 构造一个 stop_reason=tool_use 的伪响应：始终返回一个 tool_use block
    class _Block:
        type = "tool_use"
        name = "noop"
        input = {}
        id = "tu_1"

    class _Usage:
        input_tokens = 1
        output_tokens = 1

    class _Resp:
        stop_reason = "tool_use"
        content = [_Block()]
        usage = _Usage()

    call_count = 0

    def fake_call(**kwargs):
        nonlocal call_count
        call_count += 1
        return _Resp()

    agent._call_with_retry = fake_call
    agent._execute_tool = lambda *args, **kwargs: "ok"

    result = agent.run("loop forever")
    assert "[TRUNCATED]" in result
    # 调用次数应等于 max_tool_rounds + 1（最后一轮触发截断）
    assert call_count == 3
