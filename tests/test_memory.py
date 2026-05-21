"""测试 Memory 系统"""

from datetime import datetime, timezone, timedelta

from opc.schema import Message
from opc.memory import (
    EPHEMERAL_SCOPES,
    LONG_TERM_SCOPES,
    REQUIRED_MEMORY_FIELDS,
    Memory,
    MemoryRecord,
    WorkingMemory,
    delete_memory_record,
    detect_sensitive_memory_content,
    evaluate_memory_write,
    can_promote_to_long_term,
    requires_write_review,
    select_memory_for_context,
    supersede_memory_record,
    write_memory_record,
)


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




def test_select_memory_for_context_filters_expired_ephemeral_and_conflicts():
    expired = MemoryRecord(
        content="旧事实",
        scope="project",
        source="doc",
        expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    )
    run_state = MemoryRecord(content="临时状态", scope="run", source="run_trace")
    conflict = MemoryRecord(content="当前事实", scope="project", source="old-doc")
    selected = MemoryRecord(content="长期偏好", scope="user", source="manual")

    records, sources = select_memory_for_context(
        [expired, run_state, conflict, selected],
        role="engineer",
        current_facts={"当前事实"},
    )

    assert records == [selected]
    statuses = {source["status"] for source in sources}
    assert {"expired", "conflict_current_fact", "selected"} <= statuses
    assert all(source.get("scope") != "run" for source in sources)


def test_memory_record_lifecycle_fields_and_scope_sets():
    record = MemoryRecord(content="用户偏好", scope="user", source="manual-confirmation")

    assert REQUIRED_MEMORY_FIELDS <= set(record.__dataclass_fields__)
    assert record.scope in LONG_TERM_SCOPES
    assert "run" in EPHEMERAL_SCOPES
    assert record.is_long_term
    assert not record.is_expired()


def test_memory_record_expiration_and_write_review_policy():
    expired = MemoryRecord(
        content="旧决策",
        scope="project",
        source="architecture-review",
        expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    )
    run_state = MemoryRecord(content="临时 run 状态", scope="run", source="run_trace")

    assert expired.is_expired()
    assert requires_write_review(expired)
    assert can_promote_to_long_term(expired, confirmed=True)
    assert not can_promote_to_long_term(run_state, confirmed=True)
    assert not requires_write_review(run_state)




def test_memory_write_policy_rejects_sensitive_and_ephemeral_content():
    secret = MemoryRecord(content="ANTHROPIC_API_KEY=secret", scope="project", source="manual")
    temporary = MemoryRecord(content="临时 debug 结论", scope="project", source="trace")
    run_state = MemoryRecord(content="长期偏好", scope="run", source="run_trace")

    assert detect_sensitive_memory_content(secret.content) == ["api_key", "anthropic_api_key", "secret"]
    assert evaluate_memory_write(secret).action == "reject"
    assert evaluate_memory_write(temporary).reason == "ephemeral_content_rejected"
    assert evaluate_memory_write(run_state).reason == "ephemeral_scope_rejected"


def test_memory_write_policy_requires_review_before_long_term_write():
    record = MemoryRecord(content="用户偏好：使用定向测试", scope="user", source="manual")

    records, review = write_memory_record([], record, confirmed=False)
    written, decision = write_memory_record([], record, confirmed=True)

    assert records == []
    assert review.action == "review"
    assert review.audit_event["reason"] == "long_term_memory_requires_confirmation"
    assert written == [record]
    assert decision.action == "write"
    assert decision.audit_event["scope"] == "user"


def test_memory_delete_and_supersede_require_confirmed_paths():
    original = MemoryRecord(content="旧项目决策", scope="project", source="manual")
    replacement = MemoryRecord(content="新项目决策", scope="project", source="manual")

    unchanged, delete_review = delete_memory_record([original], 0, confirmed=False)
    deleted, delete_decision = delete_memory_record([original], 0, confirmed=True)
    superseded, supersede_decision = supersede_memory_record([original], 0, replacement, confirmed=True)

    assert unchanged == [original]
    assert delete_review.action == "review"
    assert deleted == []
    assert delete_decision.action == "delete"
    assert superseded[0].superseded_by == "memory:1"
    assert superseded[1] == replacement
    assert supersede_decision.action == "supersede"
