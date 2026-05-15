"""测试 P1.3 QA rework 循环改写：验证不再使用递归，且超出上限时正确中止。"""

from unittest.mock import MagicMock

import pytest

from opc.schema import QAOutput
from opc.workflow import HarnessWorkflow, _StopWorkflow


def _build_qa_output(status: str) -> QAOutput:
    return QAOutput(
        status=status,
        checked_items=[],
        evidence=[],
        defects=[] if status == "pass" else ["缺陷 X"],
        next_action="done" if status == "pass" else "rework",
    )


def test_qa_rework_loops_until_pass(tmp_path, monkeypatch):
    """QA 第一次 fail → rework → 第二次 pass，应正常返回（不递归）。"""
    wf = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)
    wf.max_rework_attempts = 5

    qa_runs = {"n": 0}

    def fake_run_stage(agent, prompt, stage_name):
        if stage_name == "待验收":
            qa_runs["n"] += 1
            return f"qa_round_{qa_runs['n']}"
        return "stage_output"

    wf._run_stage = fake_run_stage
    wf._build_context_pack = lambda *a, **kw: MagicMock(
        model_dump_json=lambda **kwargs: "{}"
    )
    wf._run_rework = lambda outputs, accepted: "new impl"

    # 第一次 fail，第二次 pass
    parsed_iter = iter([_build_qa_output("fail"), _build_qa_output("pass")])
    wf._parse_role_output = lambda role, content: next(parsed_iter)

    outputs = {"implementation": "impl_v1"}
    wf._exec_qa(
        outputs,
        should_skip=lambda *_: False,
        load_artifact=lambda *_: None,
    )

    assert qa_runs["n"] == 2
    assert outputs["acceptance"] == "qa_round_2"
    assert wf.workflow_state.rework_attempts == 1
    assert wf.state == "已通过"


def test_qa_rework_stops_when_exceeds_max(tmp_path):
    """连续 fail 超过 max_rework_attempts 应抛 _StopWorkflow（循环不递归）。"""
    wf = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)
    wf.max_rework_attempts = 1

    wf._run_stage = lambda agent, prompt, stage_name: "qa_out"
    wf._build_context_pack = lambda *a, **kw: MagicMock(model_dump_json=lambda **kw: "{}")
    wf._run_rework = lambda outputs, accepted: "new impl"
    wf._parse_role_output = lambda role, content: _build_qa_output("fail")

    outputs = {"implementation": "impl_v1"}
    with pytest.raises(_StopWorkflow):
        wf._exec_qa(
            outputs,
            should_skip=lambda *_: False,
            load_artifact=lambda *_: None,
        )

    # max_rework_attempts=1 表示允许 1 次返工，第 2 次 fail 时超限
    assert wf.workflow_state.rework_attempts >= 2
