"""测试 Agent 工具分发逻辑和消息缓冲区"""

from pathlib import Path
from unittest.mock import patch

import pytest

from opc.agent import Agent, TOOLS_READ_ONLY, TOOLS_READ_WRITE
from opc.schema import Message, MessageQueue


def test_read_only_tools_include_search_knowledge():
    names = {tool["name"] for tool in TOOLS_READ_ONLY}
    assert "search_knowledge" in names


@pytest.fixture
def workspace(tmp_path):
    """创建临时工作区并写入示例文件"""
    example = tmp_path / "hello.txt"
    example.write_text("hello world", encoding="utf-8")
    yield tmp_path


@pytest.fixture
def agent(workspace):
    """创建带读写工具的测试 Agent"""
    return Agent(
        role="test",
        system_prompt="你是一个测试 Agent",
        tools=TOOLS_READ_WRITE,
        project_dir=workspace,
    )


# ---- 工具分发逻辑 ----


class TestToolDispatch:
    """测试 _execute_tool 的分发行为"""

    def test_dispatch_read_file(self, agent, workspace):
        """read_file 分发到正确处理器"""
        result = agent._execute_tool("read_file", {"path": "hello.txt"})
        assert result == "hello world"

    def test_dispatch_write_file(self, agent, workspace):
        """write_file 分发到正确处理器"""
        result = agent._execute_tool("write_file", {"path": "new.txt", "content": "new content"})
        assert "已写入" in result
        assert (workspace / "new.txt").read_text() == "new content"

    def test_dispatch_edit_file(self, agent, workspace):
        """edit_file 分发到正确处理器"""
        result = agent._execute_tool(
            "edit_file",
            {"path": "hello.txt", "old_string": "hello", "new_string": "hi"},
        )
        assert "已更新" in result
        assert (workspace / "hello.txt").read_text() == "hi world"

    def test_dispatch_list_files(self, agent):
        """list_files 分发到正确处理器"""
        result = agent._execute_tool("list_files", {"pattern": "*.txt"})
        assert "hello.txt" in result

    def test_dispatch_grep(self, agent):
        """grep 分发到正确处理器"""
        result = agent._execute_tool("grep", {"pattern": "hello", "file_glob": "*.txt"})
        assert "hello" in result

    def test_dispatch_search_knowledge_without_index(self, agent):
        """search_knowledge 分发到正确处理器"""
        result = agent._execute_tool("search_knowledge", {"query": "hello"})
        assert "知识索引不存在" in result

    def test_dispatch_run_command(self, agent):
        """run_command 分发到正确处理器"""
        result = agent._execute_tool("run_command", {"command": "python --version"})
        assert "Python" in result or "exit code" in result

    def test_dispatch_unknown_tool(self, agent):
        """未知工具返回错误信息"""
        result = agent._execute_tool("nonexistent_tool", {})
        assert "未知工具" in result

    def test_dispatch_tool_exception_returns_error(self, agent):
        """处理器抛异常时返回错误信息而非向上传播"""
        with patch.object(agent, "_tool_read_file", side_effect=RuntimeError("boom")):
            result = agent._execute_tool("read_file", {"path": "hello.txt"})
            assert "工具执行错误" in result
            assert "boom" in result


# ---- 消息缓冲区 ----


class TestMessageBuffer:
    """测试 Agent 消息缓冲区（receive / has_pending_messages / msg_buffer）"""

    def test_initial_buffer_is_empty(self, agent):
        """Agent 初始化时消息缓冲区为空"""
        assert agent.has_pending_messages() is False
        assert len(agent.msg_buffer) == 0

    def test_receive_adds_message(self, agent):
        """receive 将消息添加到缓冲区"""
        msg = Message(content="任务开始", role="pm")
        agent.receive(msg)
        assert agent.has_pending_messages() is True
        assert len(agent.msg_buffer) == 1

    def test_receive_preserves_order(self, agent):
        """多条消息按接收顺序排列"""
        msg1 = Message(content="第一条", role="pm")
        msg2 = Message(content="第二条", role="engineer")
        agent.receive(msg1)
        agent.receive(msg2)

        pending = agent.msg_buffer.pop_all()
        assert pending[0].content == "第一条"
        assert pending[1].content == "第二条"

    def test_has_pending_after_pop_all(self, agent):
        """pop_all 后 has_pending_messages 返回 False"""
        agent.receive(Message(content="msg", role="pm"))
        assert agent.has_pending_messages() is True
        agent.msg_buffer.pop_all()
        assert agent.has_pending_messages() is False

    def test_receive_with_routing_info(self, agent):
        """接收带 send_to 的消息后可通过 is_sent_to 过滤"""
        agent.receive(Message(content="给测试", role="pm", send_to="test"))
        agent.receive(Message(content="广播", role="ceo", send_to="all"))

        messages = agent.msg_buffer.pop_all()
        to_test = [m for m in messages if m.is_sent_to("test")]
        assert len(to_test) == 2

        to_other = [m for m in messages if m.is_sent_to("other_role")]
        assert len(to_other) == 1  # 只有 "all" 的那条匹配
