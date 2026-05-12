"""测试运行指标统计。"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from opc.agent import Agent
from opc.workflow import HarnessWorkflow, WorkflowState, generate_metrics


def test_agent_run_accumulates_tokens():
    agent = Agent(role="test", system_prompt="test")
    response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(text="done")],
        usage=SimpleNamespace(input_tokens=12, output_tokens=5),
    )
    with patch.object(agent, "_call_with_retry", return_value=response):
        assert agent.run("hello") == "done"

    assert agent.last_input_tokens == 12
    assert agent.last_output_tokens == 5
    assert agent.last_api_calls == 1


def test_workflow_stage_metrics_include_duration_and_tokens(tmp_path):
    wf = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)
    agent = MagicMock()
    agent.run.return_value = "result"
    agent.last_input_tokens = 3
    agent.last_output_tokens = 7
    agent.last_tool_calls = 2
    agent.last_api_calls = 1

    assert wf._run_stage(agent, "prompt", "已定义") == "result"

    metrics = wf.workflow_state.stage_logs["已定义"]
    assert metrics["input_tokens"] == 3
    assert metrics["output_tokens"] == 7
    assert metrics["tool_calls"] == 2
    assert metrics["api_calls"] == 1
    assert metrics["duration_seconds"] >= 0


def test_generate_metrics_writes_json(tmp_path):
    state = WorkflowState(
        current_stage="已复盘",
        task_description="测试任务",
        stage_logs={
            "已定义": {"input_tokens": 10, "output_tokens": 2, "duration_seconds": 1.5, "tool_calls": 1, "api_calls": 1},
            "实现中": {"input_tokens": 5, "output_tokens": 3, "duration_seconds": 2.0, "tool_calls": 4, "api_calls": 2},
        },
    )
    path = generate_metrics(state, tmp_path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["totals"]["input_tokens"] == 15
    assert data["totals"]["output_tokens"] == 5
    assert data["totals"]["duration_seconds"] == 3.5
    assert data["totals"]["tool_calls"] == 5
    assert data["totals"]["api_calls"] == 3
