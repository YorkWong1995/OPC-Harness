"""测试工具调用和结果的持久化"""

import json
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

from opc.agent import Agent
from opc.run_store import RunStore


def test_tool_call_recording(tmp_path):
    """测试工具调用被正确记录到 audit_log"""
    agent = Agent(
        role="test_agent",
        system_prompt="You are a test agent",
        tools=[],
        project_dir=tmp_path,
    )

    # 模拟工具调用
    agent._record_tool_call(
        name="read_file",
        inputs={"file_path": "test.txt"},
        result="file content",
        elapsed=0.123,
        tool_use_id="tool_123",
        error=None
    )

    assert len(agent.audit_log) == 1
    record = agent.audit_log[0]
    assert record["tool_name"] == "read_file"
    assert record["inputs"] == {"file_path": "test.txt"}
    assert record["result"] == "file content"
    assert record["elapsed"] == 0.123
    assert record["tool_use_id"] == "tool_123"
    assert record["error"] is None


def test_tool_call_error_recording(tmp_path):
    """测试工具调用失败被正确记录"""
    agent = Agent(
        role="test_agent",
        system_prompt="You are a test agent",
        tools=[],
        project_dir=tmp_path,
    )

    agent._record_tool_call(
        name="run_command",
        inputs={"command": "bad_cmd"},
        result=None,
        elapsed=0.05,
        tool_use_id="tool_456",
        error="Command not found"
    )

    assert len(agent.audit_log) == 1
    record = agent.audit_log[0]
    assert record["tool_name"] == "run_command"
    assert record["result"] is None
    assert record["error"] == "Command not found"


def test_tool_calls_persisted_to_run_store(tmp_path):
    """测试工具调用记录被写入 RunStore"""
    store = RunStore(tmp_path / "artifacts")

    # 模拟 agent 的 audit_log
    mock_agent = Mock()
    mock_agent.role = "engineer"
    mock_agent.audit_log = [
        {
            "tool_name": "read_file",
            "inputs": {"file_path": "src/main.py"},
            "result": "print('hello')",
            "elapsed": 0.01,
            "tool_use_id": "t1",
            "error": None,
        },
        {
            "tool_name": "write_file",
            "inputs": {"file_path": "src/main.py", "content": "print('world')"},
            "result": "已写入 src/main.py（14 字符）",
            "elapsed": 0.02,
            "tool_use_id": "t2",
            "error": None,
        },
    ]

    # 模拟 workflow 中的持久化逻辑
    for tool_record in mock_agent.audit_log:
        store.append("tool_call", stage="engineer", role="engineer", **tool_record)

    # 验证事件被记录
    assert len(store.events) == 2
    assert store.events[0].type == "tool_call"
    assert store.events[0].payload["tool_name"] == "read_file"
    assert store.events[1].payload["tool_name"] == "write_file"

    # 验证持久化到文件
    events_path = tmp_path / "artifacts" / "run_events.jsonl"
    assert events_path.exists()
    lines = events_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    event_data = json.loads(lines[0])
    assert event_data["type"] == "tool_call"
    assert event_data["payload"]["tool_name"] == "read_file"


def test_tool_result_truncation(tmp_path):
    """测试工具结果超长时被截断"""
    agent = Agent(
        role="test_agent",
        system_prompt="You are a test agent",
        tools=[],
        project_dir=tmp_path,
    )

    long_result = "x" * 1000
    agent._record_tool_call(
        name="read_file",
        inputs={"file_path": "big.txt"},
        result=long_result,
        elapsed=0.1,
        tool_use_id="t3",
        error=None
    )

    record = agent.audit_log[0]
    assert len(record["result"]) == 500
