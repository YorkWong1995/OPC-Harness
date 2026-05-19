import asyncio
import json
from unittest.mock import MagicMock

import pytest

from opc.agent import Agent
from opc.roles import (
    ROLE_TOOL_NAMES,
    create_architect_agent,
    create_engineer_agent,
    create_ops_agent,
    create_pm_agent,
    create_qa_agent,
)
from opc.schema import ContextPack, QAOutput, StageSummary
from opc.store import Store
from opc.workflow import HarnessWorkflow, WorkflowState, _StopWorkflow, generate_metrics


def _tool_names(agent):
    return {tool["name"] for tool in (agent.tools or [])}


def test_role_tool_policies_are_explicit(tmp_path):
    assert _tool_names(create_pm_agent()) == ROLE_TOOL_NAMES["pm"]
    assert _tool_names(create_architect_agent(tmp_path)) == ROLE_TOOL_NAMES["architect"]
    assert _tool_names(create_qa_agent(tmp_path)) == ROLE_TOOL_NAMES["qa"]
    assert _tool_names(create_ops_agent(tmp_path)) == ROLE_TOOL_NAMES["ops"]
    assert _tool_names(create_engineer_agent(tmp_path)) == ROLE_TOOL_NAMES["engineer"]
    assert "write_file" not in ROLE_TOOL_NAMES["qa"]
    assert "run_tests" in ROLE_TOOL_NAMES["qa"]


def test_context_pack_is_tailored_by_role(tmp_path):
    workflow = HarnessWorkflow(task="ship beta", project_dir=tmp_path, auto_confirm=True)
    workflow.stage_summaries["pm"] = StageSummary(
        stage="pm",
        goal="ship beta",
        decisions=["use beta checklist"],
        changed_files=["src/opc/schema.py"],
        validation=["python -m pytest tests/test_qa_output_validator.py"],
        risks=["risk"],
    )

    pm_pack = workflow._build_context_pack("pm", "已定义", "raw detail")
    qa_pack = workflow._build_context_pack("qa", "待验收", "raw detail")

    assert pm_pack.related_files == []
    assert pm_pack.stage_summary == {}
    assert pm_pack.diff_summary == ""
    assert qa_pack.related_files
    assert qa_pack.validation
    assert qa_pack.diff_summary == "raw detail"


def test_tool_result_summary_bounds_noisy_output(tmp_path):
    agent = Agent(role="test", system_prompt="test", project_dir=tmp_path)
    summary = agent._summarize_tool_result("grep", "x" * 800)

    assert summary["truncated"] is True
    assert summary["original_chars"] == 800
    assert len(summary["preview"]) == 500
    assert "original_chars=800" in summary["content"]


def test_store_versions_artifacts(tmp_path):
    store = Store(tmp_path)
    first = store.save("implementation.md", "v1")
    second = store.save("implementation.md", "v2")

    manifest = json.loads((tmp_path / "artifact_versions.json").read_text(encoding="utf-8"))
    assert first == second == tmp_path / "implementation.md"
    assert (tmp_path / "implementation.v1.md").read_text(encoding="utf-8") == "v1"
    assert (tmp_path / "implementation.v2.md").read_text(encoding="utf-8") == "v2"
    assert manifest["implementation.md"]["versions"] == ["implementation.v1.md", "implementation.v2.md"]


def test_qa_diagnostics_and_validation_evidence_are_traced(tmp_path):
    workflow = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)
    workflow.max_rework_attempts = 0
    workflow.qa = MagicMock()
    workflow._build_context_pack = lambda *args, **kwargs: ContextPack(validation=["python -m pytest tests/test_x.py"])

    async def fake_run_stage(agent, prompt, stage_name):
        return json.dumps({
            "status": "fail",
            "checked_items": ["unit"],
            "evidence": ["pytest failed"],
            "defects": ["bug"],
            "next_action": "rework",
            "failure_root_cause": "implementation_bug",
            "rollback_stage": "engineer",
            "diagnostic_summary": "Engineer should fix bug",
        })

    workflow._run_stage = fake_run_stage

    with pytest.raises(_StopWorkflow):
        asyncio.run(workflow._exec_qa(
            {"implementation": "impl"},
            should_skip=lambda *_: False,
            load_artifact=lambda *_: None,
        ))

    events = {event.type: event.payload for event in workflow.run_store.events}
    assert events["validation_evidence"]["commands"] == ["python -m pytest tests/test_x.py"]
    assert events["qa_failed"]["failure_root_cause"] == "implementation_bug"
    assert events["qa_failed"]["rollback_stage"] == "engineer"


def test_qa_output_accepts_diagnostic_fields():
    output = QAOutput(
        status="fail",
        next_action="rework",
        defects=["bug"],
        failure_root_cause="implementation_bug",
        rollback_stage="engineer",
        diagnostic_summary="fix implementation",
    )

    assert output.failure_root_cause == "implementation_bug"
    assert output.rollback_stage == "engineer"


def test_self_repair_and_validation_metrics_are_recorded(tmp_path):
    workflow = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)

    with pytest.raises(_StopWorkflow):
        workflow._parse_role_output("pm", "not json")

    assert any(event.type == "self_repair_attempted" for event in workflow.run_store.events)

    state = WorkflowState(task_description="t")
    state.stage_logs["_validation_runs"] = 2
    state.stage_logs["_self_repair_attempts"] = 1
    state.stage_logs["_self_repair_successes"] = 0
    metrics_path = generate_metrics(state, tmp_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert metrics["quality"]["validation_runs"] == 2
    assert metrics["quality"]["self_repair_attempts"] == 1
    assert metrics["quality"]["self_repair_successes"] == 0
