"""测试最小 workflow spec"""

from opc.workflow_spec import DEFAULT_WORKFLOW_SPEC, WorkflowSpec, Transition


def test_default_spec_qa_pass():
    """QA pass 流转到已通过"""
    spec = DEFAULT_WORKFLOW_SPEC
    assert spec.next_state("待验收", "pass") == "已通过"


def test_default_spec_qa_fail():
    """QA fail 流转到已退回"""
    spec = DEFAULT_WORKFLOW_SPEC
    assert spec.next_state("待验收", "fail") == "已退回"


def test_rework_returns_to_engineer():
    """退回后重新进入实现"""
    spec = DEFAULT_WORKFLOW_SPEC
    assert spec.next_state("已退回", "pass") == "实现中"


def test_terminal_state():
    """已复盘是终态"""
    spec = DEFAULT_WORKFLOW_SPEC
    assert spec.is_terminal("已复盘")
    assert not spec.is_terminal("待验收")


def test_unknown_transition_returns_none():
    """未定义的流转返回 None"""
    spec = DEFAULT_WORKFLOW_SPEC
    assert spec.next_state("已复盘", "pass") is None
    assert spec.next_state("待澄清", "fail") is None


def test_custom_spec():
    """自定义 spec"""
    spec = WorkflowSpec(
        name="simple",
        states=["start", "end"],
        transitions=[Transition("start", "pass", "end")],
        initial_state="start",
        terminal_states=["end"],
    )
    assert spec.next_state("start", "pass") == "end"
    assert spec.is_terminal("end")
