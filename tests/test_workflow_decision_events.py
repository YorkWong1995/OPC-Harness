from unittest.mock import MagicMock, patch

import pytest

from opc.workflow import HarnessWorkflow, _StopWorkflow


def _workflow(tmp_path, *, auto_confirm=True):
    with (
        patch("opc.workflow.create_pm_agent", return_value=MagicMock()),
        patch("opc.workflow.create_engineer_agent", return_value=MagicMock()),
        patch("opc.workflow.create_embedded_engineer_agent", return_value=MagicMock()),
        patch("opc.workflow.create_qa_agent", return_value=MagicMock()),
    ):
        return HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=auto_confirm, roles=set())


def _events(workflow, event_type):
    return [event for event in workflow.run_store.events if event.type == event_type]


def test_auto_confirm_records_approval_decision(tmp_path):
    workflow = _workflow(tmp_path, auto_confirm=True)

    assert workflow.review("PM 已产出 PRD，是否继续？", "content") == "y"

    approval = _events(workflow, "approval_required")[0]
    decision = _events(workflow, "approval_decision")[0]
    assert approval.payload["mode"] == "auto_confirm"
    assert approval.payload["default_action"] == "continue"
    assert decision.payload["decision"] == "y"
    assert decision.payload["result"] == "continued"


def test_cost_hard_limit_opens_circuit_breaker(tmp_path):
    workflow = _workflow(tmp_path)
    workflow.opc_config.cost.enforce_hard_limit = True
    workflow.opc_config.cost.role_token_hard_limit = 1

    with pytest.raises(_StopWorkflow):
        workflow._observe_cost_limits("pm", stage_tokens=2, stage_api_calls=0)

    breaker = _events(workflow, "circuit_breaker_open")[0]
    assert breaker.payload["reason"] == "role_token_hard_limit"
    assert breaker.payload["stage"] == "pm"
    assert breaker.payload["default_action"] == "stop_workflow"


def test_qa_failure_records_rollback_decision(tmp_path):
    workflow = _workflow(tmp_path)

    workflow._record_rollback_decision(
        from_stage="qa",
        to_stage="engineer",
        reason="qa_failed",
        default_action="rework",
        rework_attempts=1,
    )

    decision = _events(workflow, "rollback_decision")[0]
    assert decision.payload["from_stage"] == "qa"
    assert decision.payload["to_stage"] == "engineer"
    assert decision.payload["reason"] == "qa_failed"
    assert decision.payload["default_action"] == "rework"
