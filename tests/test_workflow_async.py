"""测试 P1.1：HarnessWorkflow.run 可在 async 上下文中调用。"""

import asyncio
from unittest.mock import MagicMock, patch

from opc.workflow import HarnessWorkflow


def test_workflow_run_inside_async_context(tmp_path):
    """Web UI/FastAPI 等 async 上下文中 await workflow.run() 不应触发 asyncio.run 嵌套错误。"""
    async def run_workflow():
        mocks = {
            "pm": MagicMock(),
            "engineer": MagicMock(),
            "qa": MagicMock(),
        }
        mocks["pm"].run.side_effect = [
            '{"background":"b","goal":"g","scope":[],"non_goals":[],"acceptance_criteria":["ok"],"risks":[]}',
            "retro",
        ]
        mocks["engineer"].run.return_value = (
            '{"changed_files":[],"implementation_summary":"done","test_result":"not run",'
            '"known_limits":[],"failure_reason":""}'
        )
        mocks["qa"].run.return_value = (
            '{"status":"pass","checked_items":["ok"],"evidence":["mock"],'
            '"defects":[],"next_action":"done"}'
        )

        with (
            patch("opc.workflow.create_pm_agent", return_value=mocks["pm"]),
            patch("opc.workflow.create_engineer_agent", return_value=mocks["engineer"]),
            patch("opc.workflow.create_embedded_engineer_agent", return_value=mocks["engineer"]),
            patch("opc.workflow.create_qa_agent", return_value=mocks["qa"]),
        ):
            workflow = HarnessWorkflow(
                task="t",
                project_dir=tmp_path,
                auto_confirm=True,
                roles=set(),
            )
            await workflow.run()

        assert workflow.state == "已复盘"

    asyncio.run(run_workflow())
