"""测试 Environment 消息总线"""

import json
from pathlib import Path
from opc.schema import Message
from opc.environment import Environment
from opc.agent import Agent


def test_environment_basic():
    """测试 Environment 基本功能"""
    env = Environment(project_dir=Path("."))

    # 创建简单的 Agent（不需要实际调用 API）
    pm_agent = Agent(
        role="pm",
        system_prompt="You are a PM",
        project_dir=Path("."),
    )
    engineer_agent = Agent(
        role="engineer",
        system_prompt="You are an Engineer",
        project_dir=Path("."),
    )

    # 添加角色
    env.add_role("pm", pm_agent)
    env.add_role("engineer", engineer_agent)

    assert len(env.roles) == 2
    assert "pm" in env.roles
    assert "engineer" in env.roles


def test_message_publishing():
    """测试消息发布和路由"""
    env = Environment()

    pm_agent = Agent(role="pm", system_prompt="PM")
    engineer_agent = Agent(role="engineer", system_prompt="Engineer")
    qa_agent = Agent(role="qa", system_prompt="QA")

    env.add_role("pm", pm_agent)
    env.add_role("engineer", engineer_agent)
    env.add_role("qa", qa_agent)

    # 发布广播消息
    msg1 = Message(content="PRD 已完成", role="pm", send_to="all", cause_by="prd_definition")
    env.publish(msg1)

    # 所有角色都应该收到消息
    assert len(pm_agent.msg_buffer) == 1
    assert len(engineer_agent.msg_buffer) == 1
    assert len(qa_agent.msg_buffer) == 1

    # 发布定向消息
    msg2 = Message(content="请实现功能", role="pm", send_to="engineer")
    env.publish(msg2)

    # 只有 engineer 收到
    assert len(pm_agent.msg_buffer) == 1  # 没有新消息
    assert len(engineer_agent.msg_buffer) == 2  # 收到新消息
    assert len(qa_agent.msg_buffer) == 1  # 没有新消息

    # 检查消息历史
    history = env.get_history()
    assert len(history) == 2


def test_message_subscription():
    """测试消息订阅"""
    env = Environment()

    pm_agent = Agent(role="pm", system_prompt="PM")
    engineer_agent = Agent(role="engineer", system_prompt="Engineer")

    env.add_role("pm", pm_agent)
    env.add_role("engineer", engineer_agent)

    # Engineer 只订阅 PRD 相关消息
    env.subscribe("engineer", {"prd_definition", "pm"})

    # 发布 PRD 消息
    msg1 = Message(content="PRD", role="pm", cause_by="prd_definition")
    env.publish(msg1)

    # Engineer 应该收到
    assert len(engineer_agent.msg_buffer) == 1

    # 发布其他消息
    msg2 = Message(content="其他消息", role="qa", cause_by="qa_review")
    env.publish(msg2)

    # Engineer 不应该收到
    assert len(engineer_agent.msg_buffer) == 1  # 没有新消息


def test_publish_rejects_unknown_send_to():
    env = Environment()
    env.add_role("pm", Agent(role="pm", system_prompt="PM"))

    msg = Message(content="x", role="pm", send_to="ghost")

    try:
        env.publish(msg)
    except ValueError as error:
        assert "非法 send_to" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_publish_rejects_unknown_cause_by():
    env = Environment()
    env.add_role("pm", Agent(role="pm", system_prompt="PM"))

    msg = Message(content="x", role="pm", cause_by="unknown_action")

    try:
        env.publish(msg)
    except ValueError as error:
        assert "非法 cause_by" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_environment_persists_message_history_and_buffers(tmp_path: Path):
    env = Environment(project_dir=tmp_path)
    engineer_agent = Agent(role="engineer", system_prompt="Engineer")
    env.add_role("engineer", engineer_agent)

    message = Message(
        content="PRD 已完成",
        role="pm",
        send_to="engineer",
        cause_by="prd_definition",
    )
    env.publish(message)

    events_path = tmp_path / "artifacts" / "run_events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]

    assert [event["type"] for event in events] == ["message_published", "message_delivered"]
    assert events[0]["payload"]["message"]["content"] == "PRD 已完成"
    assert events[1]["payload"]["recipient"] == "engineer"
    assert events[1]["payload"]["buffer_size"] == 1
    assert (tmp_path / "artifacts" / "run_trace.json").exists()


def test_environment_history():
    """测试消息历史"""
    env = Environment()

    pm_agent = Agent(role="pm", system_prompt="PM")
    env.add_role("pm", pm_agent)

    # 发布多条消息
    for i in range(5):
        msg = Message(content=f"消息{i}", role="pm")
        env.publish(msg)

    # 获取所有历史
    history = env.get_history()
    assert len(history) == 5

    # 获取限制数量的历史
    history = env.get_history(limit=3)
    assert len(history) == 3
    assert history[-1].content == "消息4"  # 最新的消息

    # 按角色过滤
    engineer_agent = Agent(role="engineer", system_prompt="Engineer")
    env.add_role("engineer", engineer_agent)
    env.publish(Message(content="工程师消息", role="engineer"))

    pm_history = env.get_history(role="pm")
    assert len(pm_history) == 5
    assert all(msg.role == "pm" for msg in pm_history)
