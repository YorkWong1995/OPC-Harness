"""测试 P2.6：私有流程控制异常由 workflow 主循环消费。"""

import asyncio
from unittest.mock import MagicMock, patch

from opc.workflow import HarnessWorkflow, _GoBack, _StopWorkflow


def _workflow(tmp_path):
    with (
        patch("opc.workflow.create_pm_agent", return_value=MagicMock()),
        patch("opc.workflow.create_engineer_agent", return_value=MagicMock()),
        patch("opc.workflow.create_embedded_engineer_agent", return_value=MagicMock()),
        patch("opc.workflow.create_qa_agent", return_value=MagicMock()),
    ):
        return HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True, roles=set())


def test_stop_workflow_signal_is_consumed_by_main_loop(tmp_path):
    workflow = _workflow(tmp_path)
    calls = []

    async def stop_at_first_stage(stage, *_args):
        calls.append(stage)
        raise _StopWorkflow()

    workflow._run_stage_by_name = stop_at_first_stage

    asyncio.run(workflow.run())

    assert calls == ["pm"]


def test_go_back_signal_rewinds_to_previous_stage(tmp_path):
    workflow = _workflow(tmp_path)
    calls = []
    engineer_attempts = 0

    async def run_stage(stage, *_args):
        nonlocal engineer_attempts
        calls.append(stage)
        if stage == "engineer":
            engineer_attempts += 1
            if engineer_attempts == 1:
                raise _GoBack()
        if calls == ["pm", "engineer", "pm"]:
            raise _StopWorkflow()

    workflow._run_stage_by_name = run_stage

    asyncio.run(workflow.run())

    assert calls == ["pm", "engineer", "pm"]
