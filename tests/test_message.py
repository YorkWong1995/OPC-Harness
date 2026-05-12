"""测试 Message 和 MessageQueue"""

from opc.schema import Message, MessageQueue


def test_message_creation():
    """测试消息创建"""
    msg = Message(
        content="这是一个测试消息",
        role="pm",
        cause_by="prd_definition",
        send_to="engineer",
        metadata={"priority": "high"},
    )

    assert msg.content == "这是一个测试消息"
    assert msg.role == "pm"
    assert msg.cause_by == "prd_definition"
    assert msg.send_to == "engineer"
    assert msg.metadata["priority"] == "high"
    assert msg.timestamp is not None


def test_message_routing():
    """测试消息路由"""
    # 发送给特定角色
    msg1 = Message(content="给 engineer", role="pm", send_to="engineer")
    assert msg1.is_sent_to("engineer") is True
    assert msg1.is_sent_to("qa") is False

    # 广播消息
    msg2 = Message(content="广播消息", role="pm", send_to="all")
    assert msg2.is_sent_to("engineer") is True
    assert msg2.is_sent_to("qa") is True

    # 默认广播
    msg3 = Message(content="默认广播", role="pm")
    assert msg3.is_sent_to("engineer") is True
    assert msg3.is_sent_to("qa") is True


def test_message_queue():
    """测试消息队列"""
    queue = MessageQueue()

    # 测试空队列
    assert len(queue) == 0
    assert bool(queue) is False
    assert queue.pop() is None

    # 添加消息
    msg1 = Message(content="消息1", role="pm")
    msg2 = Message(content="消息2", role="engineer")
    queue.push(msg1)
    queue.push(msg2)

    assert len(queue) == 2
    assert bool(queue) is True

    # 查看队首
    peeked = queue.peek()
    assert peeked.content == "消息1"
    assert len(queue) == 2  # peek 不移除

    # 取出消息
    popped = queue.pop()
    assert popped.content == "消息1"
    assert len(queue) == 1

    # 取出所有消息
    all_msgs = queue.pop_all()
    assert len(all_msgs) == 1
    assert all_msgs[0].content == "消息2"
    assert len(queue) == 0
