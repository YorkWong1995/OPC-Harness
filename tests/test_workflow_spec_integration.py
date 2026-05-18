"""测试 P1.2：HarnessWorkflow 使用 WorkflowSpec 决定主链路状态流转。"""

from unittest.mock import MagicMock, patch

import pytest

from opc.workflow import HarnessWorkflow


@pytest.fixture
def workflow(tmp_path):
    with (
        patch("opc.workflow.create_pm_agent", return_value=MagicMock()),
        patch("opc.workflow.create_engineer_agent", return_value=MagicMock()),
        patch("opc.workflow.create_embedded_engineer_agent", return_value=MagicMock()),
        patch("opc.workflow.create_qa_agent", return_value=MagicMock()),
        patch("opc.workflow.create_architect_agent", return_value=MagicMock()),
        patch("opc.workflow.create_ops_agent", return_value=MagicMock()),
        patch("opc.workflow.create_growth_agent", return_value=MagicMock()),
    ):
        yield HarnessWorkflow(
            task="t",
            project_dir=tmp_path,
            auto_confirm=True,
            roles={"architect", "ops"},
        )


def test_spec_builds_core_runtime_stages(workflow):
    assert workflow.workflow_spec.runtime_stages(set()) == ["pm", "engineer", "qa", "retro"]


def test_spec_builds_optional_runtime_stages(workflow):
    assert workflow.workflow_spec.runtime_stages({"growth"}) == ["growth", "pm", "engineer", "qa", "retro"]
    assert workflow.workflow_spec.runtime_stages({"architect"}) == ["pm", "architect", "engineer", "qa", "retro"]
    assert workflow.workflow_spec.runtime_stages({"growth", "architect", "ops"}) == [
        "pm",
        "growth_architect",
        "engineer",
        "qa",
        "ops",
        "retro",
    ]


def test_spec_declares_stage_metadata(workflow):
    stages = {stage.name: stage for stage in workflow.workflow_spec.stages}
    assert stages["growth"].parallel_group == "growth_architect"
    assert stages["architect"].optional_role == "architect"
    assert stages["retro"].approval_required is False

def test_spec_drives_core_pm_to_engineer(workflow):
    stages = ["pm", "engineer", "qa", "retro"]
    assert workflow._next_stage_index(stages, 0) == 1


def test_spec_collapses_qa_pass_state_to_retro(workflow):
    stages = ["pm", "engineer", "qa", "retro"]
    assert workflow._next_stage_index(stages, 2) == 3


def test_spec_does_not_skip_runtime_inserted_architect(workflow):
    stages = ["pm", "architect", "engineer", "qa", "retro"]
    assert workflow._next_stage_index(stages, 0) == 1


def test_spec_does_not_skip_runtime_inserted_ops_after_qa(workflow):
    stages = ["pm", "engineer", "qa", "ops", "retro"]
    assert workflow._next_stage_index(stages, 2) == 3


@pytest.mark.parametrize(
    ("stage", "expected_state"),
    [
        ("pm", "已定义"),
        ("engineer", "实现中"),
        ("qa", "待验收"),
        ("retro", "已复盘"),
    ],
)
def test_stage_to_state_mapping(stage, expected_state):
    assert HarnessWorkflow._stage_to_state_name(stage) == expected_state
