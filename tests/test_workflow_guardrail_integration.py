from unittest.mock import MagicMock, patch

from opc.workflow import HarnessWorkflow


def _agent():
    agent = MagicMock()
    agent.run_store = None
    agent.guardrail_policy = None
    return agent


def test_workflow_injects_run_store_and_security_policy(tmp_path):
    agents = {name: _agent() for name in ["pm", "engineer", "qa", "architect", "ops", "growth"]}
    (tmp_path / "opc.toml").write_text(
        "[security]\npermission_profile = 'read-only'\ndangerous_command_policy = 'approval'\n",
        encoding="utf-8",
    )
    with (
        patch("opc.workflow.create_pm_agent", return_value=agents["pm"]),
        patch("opc.workflow.create_engineer_agent", return_value=agents["engineer"]),
        patch("opc.workflow.create_embedded_engineer_agent", return_value=agents["engineer"]),
        patch("opc.workflow.create_qa_agent", return_value=agents["qa"]),
        patch("opc.workflow.create_architect_agent", return_value=agents["architect"]),
        patch("opc.workflow.create_ops_agent", return_value=agents["ops"]),
        patch("opc.workflow.create_growth_agent", return_value=agents["growth"]),
    ):
        workflow = HarnessWorkflow(task="t", project_dir=tmp_path, roles={"architect", "ops", "growth"})

    for agent in agents.values():
        assert agent.run_store is workflow.run_store
        assert agent.guardrail_policy.profile == "read-only"
        assert agent.guardrail_policy.dangerous_command_policy == "approval"
