"""测试 Memory 系统"""

from opc.schema import Message
from opc.memory import Memory, WorkingMemory


def test_memory_basic():
    """测试 Memory 基本功能"""
    memory = Memory()

    msg1 = Message(content="PRD", role="pm", cause_by="write_prd")
    msg2 = Message(content="实现", role="engineer", cause_by="implement")
    msg3 = Message(content="验收", role="qa", cause_by="review")

    memory.add(msg1)
    memory.add(msg2)
    memory.add(msg3)

    assert len(memory) == 3

    all_msgs = memory.get()
    assert len(all_msgs) == 3

    recent = memory.get(limit=2)
    assert len(recent) == 2
    assert recent[-1].content == "验收"


def test_memory_by_role():
    """测试按角色检索"""
    memory = Memory()

    memory.add(Message(content="PRD1", role="pm"))
    memory.add(Message(content="实现1", role="engineer"))
    memory.add(Message(content="PRD2", role="pm"))
    memory.add(Message(content="实现2", role="engineer"))
    memory.add(Message(content="验收", role="qa"))

    pm_msgs = memory.get_by_role("pm")
    assert len(pm_msgs) == 2
    assert all(msg.role == "pm" for msg in pm_msgs)

    engineer_msgs = memory.get_by_role("engineer")
    assert len(engineer_msgs) == 2

    qa_msgs = memory.get_by_role("qa")
    assert len(qa_msgs) == 1

    pm_recent = memory.get_by_role("pm", limit=1)
    assert len(pm_recent) == 1
    assert pm_recent[0].content == "PRD2"


def test_memory_by_actions():
    """测试按 Action 检索"""
    memory = Memory()

    memory.add(Message(content="PRD", role="pm", cause_by="write_prd"))
    memory.add(Message(content="架构", role="architect", cause_by="design"))
    memory.add(Message(content="实现", role="engineer", cause_by="implement"))
    memory.add(Message(content="验收", role="qa", cause_by="review"))

    prd_msgs = memory.get_by_actions({"write_prd"})
    assert len(prd_msgs) == 1
    assert prd_msgs[0].content == "PRD"

    dev_msgs = memory.get_by_actions({"design", "implement"})
    assert len(dev_msgs) == 2


def test_memory_search():
    """测试关键词搜索"""
    memory = Memory()

    memory.add(Message(content="实现用户登录功能", role="engineer"))
    memory.add(Message(content="实现用户注册功能", role="engineer"))
    memory.add(Message(content="实现数据导出功能", role="engineer"))
    memory.add(Message(content="验收登录功能", role="qa"))

    login_msgs = memory.search("登录")
    assert len(login_msgs) == 2

    user_msgs = memory.search("用户")
    assert len(user_msgs) == 2

    limited = memory.search("实现", limit=2)
    assert len(limited) == 2


def test_working_memory():
    """测试工作记忆"""
    working_memory = WorkingMemory(max_size=3)

    working_memory.add(Message(content="消息1", role="pm"))
    working_memory.add(Message(content="消息2", role="pm"))
    working_memory.add(Message(content="消息3", role="pm"))

    assert len(working_memory) == 3
    assert working_memory.is_full()

    working_memory.add(Message(content="消息4", role="pm"))

    assert len(working_memory) == 3
    assert working_memory.is_full()

    all_msgs = working_memory.get()
    assert all_msgs[0].content == "消息2"
    assert all_msgs[-1].content == "消息4"


def test_memory_recent():
    """测试获取最近消息"""
    memory = Memory()

    for i in range(10):
        memory.add(Message(content=f"消息{i}", role="pm"))

    recent = memory.get_recent(5)
    assert len(recent) == 5
    assert recent[0].content == "消息5"
    assert recent[-1].content == "消息9"
