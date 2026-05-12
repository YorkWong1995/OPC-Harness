"""Tests for role output contracts and QA rework."""

from unittest.mock import MagicMock, patch

import pytest

from opc.schema import Message, parse_role_output
from opc.workflow import HarnessWorkflow


def _make_agent_mock(return_value="模拟输出"):
    agent = MagicMock()
    agent.run.return_value = return_value
    return agent


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path


@pytest.fixture
def mock_agents():
    mocks = {
        "pm": _make_agent_mock('{"background":"b","goal":"g","scope":[],"non_goals":[],"acceptance_criteria":["ok"],"risks":[]}'),
        "engineer": _make_agent_mock('{"changed_files":[],"implementation_summary":"done","test_result":"not run","known_limits":[],"failure_reason":""}'),
        "qa": _make_agent_mock('{"status":"pass","checked_items":["ok"],"evidence":["mock"],"defects":[],"next_action":"done"}'),
        "architect": _make_agent_mock("模拟架构"),
        "ceo": _make_agent_mock("批准"),
        "ops": _make_agent_mock("模拟Ops"),
        "growth": _make_agent_mock("模拟Growth"),
    }
    with (
        patch("opc.workflow.create_pm_agent", return_value=mocks["pm"]),
        patch("opc.workflow.create_engineer_agent", return_value=mocks["engineer"]),
        patch("opc.workflow.create_embedded_engineer_agent", return_value=mocks["engineer"]),
        patch("opc.workflow.create_qa_agent", return_value=mocks["qa"]),
        patch("opc.workflow.create_architect_agent", return_value=mocks["architect"]),
        patch("opc.workflow.create_ceo_agent", return_value=mocks["ceo"]),
        patch("opc.workflow.create_ops_agent", return_value=mocks["ops"]),
        patch("opc.workflow.create_growth_agent", return_value=mocks["growth"]),
    ):
        yield mocks


def test_parse_pm_output_contract():
    output = parse_role_output(
        "pm",
        '{"background":"b","goal":"g","scope":["s"],"non_goals":[],"acceptance_criteria":["a"],"risks":[]}',
    )

    assert output.goal == "g"


def test_parse_qa_output_rejects_invalid_status():
    with pytest.raises(Exception):
        parse_role_output("qa", '{"status":"unknown"}')


def test_message_route_validation_rejects_unknown_target():
    with pytest.raises(ValueError):
        Message(content="x", role="pm", send_to="ghost").validate_route()


def test_qa_fail_reworks_engineer_once(project_dir, mock_agents):
    mock_agents["qa"].run.side_effect = [
        '{"status":"fail","checked_items":["ok"],"evidence":[],"defects":["缺陷"],"next_action":"rework"}',
        '{"status":"pass","checked_items":["ok"],"evidence":["fixed"],"defects":[],"next_action":"done"}',
    ]
    wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
    wf.run()

    assert wf.state == "已复盘"
    assert mock_agents["engineer"].run.call_count == 2
    assert wf.workflow_state.rework_attempts == 1
    assert (project_dir / "artifacts" / "run_trace.json").exists()
