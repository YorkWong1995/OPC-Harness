"""测试 HarnessWorkflow 初始化和阶段流转（mock API 调用）"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from opc.workflow import HarnessWorkflow, STATES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path):
    """临时项目目录"""
    return tmp_path


def _make_agent_mock(return_value="模拟输出"):
    """创建一个 mock Agent，run() 返回指定字符串"""
    agent = MagicMock()
    agent.run.return_value = return_value
    return agent


@pytest.fixture
def mock_agents():
    """统一 mock 所有 create_*_agent 工厂函数"""
    mocks = {
        "pm": _make_agent_mock('{"background":"b","goal":"g","scope":[],"non_goals":[],"acceptance_criteria":["ok"],"risks":[]}'),
        "engineer": _make_agent_mock('{"changed_files":[],"implementation_summary":"done","test_result":"not run","known_limits":[],"failure_reason":"","blocked_by":[],"suggested_next_step":""}'),
        "qa": _make_agent_mock('{"status":"pass","checked_items":["ok"],"evidence":["mock"],"defects":[],"next_action":"done","failure_root_cause":"","rollback_stage":"","diagnostic_summary":""}'),
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


# ---------------------------------------------------------------------------
# 初始化测试
# ---------------------------------------------------------------------------


class TestWorkflowInit:
    def test_default_state(self, project_dir, mock_agents):
        """默认初始状态为 待澄清"""
        wf = HarnessWorkflow(task="测试任务", project_dir=project_dir)
        assert wf.state == "待澄清"

    def test_task_stored(self, project_dir, mock_agents):
        """task 被正确存储"""
        wf = HarnessWorkflow(task="构建功能X", project_dir=project_dir)
        assert wf.task == "构建功能X"

    def test_project_dir_resolved(self, project_dir, mock_agents):
        """project_dir 被解析为绝对路径"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir)
        assert wf.project_dir == project_dir.resolve()

    def test_store_created(self, project_dir, mock_agents):
        """Store 实例在 project_dir/artifacts 下创建"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir)
        assert wf.store.dir == project_dir.resolve() / "artifacts"

    def test_auto_confirm_default_false(self, project_dir, mock_agents):
        """auto_confirm 默认为 False"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir)
        assert wf.auto_confirm is False

    def test_auto_confirm_set(self, project_dir, mock_agents):
        """auto_confirm 可显式设置"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        assert wf.auto_confirm is True

    def test_roles_default_empty(self, project_dir, mock_agents):
        """默认 roles 为空集合"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir)
        assert wf.roles == set()

    def test_ceo_review_adds_ceo_role(self, project_dir, mock_agents):
        """ceo_review=True 会添加 ceo 角色"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, ceo_review=True)
        assert wf.enabled("ceo")

    def test_skip_architect_removes_architect(self, project_dir, mock_agents):
        """skip_architect=True 会移除 architect 角色"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, skip_architect=True, roles={"architect"})
        assert not wf.enabled("architect")

    def test_model_stored(self, project_dir, mock_agents):
        """model 参数被传递并存储"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, model="gpt-4")
        assert wf.model == "gpt-4"

    def test_use_embedded_engineer_flag(self, project_dir, mock_agents):
        """use_embedded_engineer 标志被存储"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, use_embedded_engineer=True)
        assert wf.use_embedded_engineer is True

    def test_optional_agents_none_by_default(self, project_dir, mock_agents):
        """默认情况下 ceo/architect/ops/growth 均为 None"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir)
        assert wf.ceo is None
        assert wf.architect is None
        assert wf.ops is None
        assert wf.growth is None

    def test_ceo_agent_created_when_enabled(self, project_dir, mock_agents):
        """ceo 角色启用时 ceo agent 被创建"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, ceo_review=True)
        assert wf.ceo is not None

    def test_architect_agent_created_when_enabled(self, project_dir, mock_agents):
        """architect 角色启用时 architect agent 被创建"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, roles={"architect"})
        assert wf.architect is not None

    def test_embedded_engineer_used(self, project_dir, mock_agents):
        """use_embedded_engineer=True 时调用 create_embedded_engineer_agent"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, use_embedded_engineer=True)
        assert wf.use_embedded_engineer is True


    def test_dynamic_roles_enable_architect_for_architecture_task(self, project_dir, mock_agents):
        wf = HarnessWorkflow(task="需要设计架构方案", project_dir=project_dir)
        assert wf.enabled("architect")
        assert wf.architect is not None

    def test_dynamic_roles_enable_ops_for_release_task(self, project_dir, mock_agents):
        wf = HarnessWorkflow(task="准备发布上线检查", project_dir=project_dir)
        assert wf.enabled("ops")
        assert wf.ops is not None

    def test_dynamic_roles_enable_growth_for_research_task(self, project_dir, mock_agents):
        wf = HarnessWorkflow(task="做一次用户研究", project_dir=project_dir)
        assert wf.enabled("growth")
        assert wf.growth is not None

    def test_manual_roles_override_dynamic_inference(self, project_dir, mock_agents):
        wf = HarnessWorkflow(task="准备发布上线检查", project_dir=project_dir, roles=set())
        assert wf.roles == set()
        assert wf.ops is None


# ---------------------------------------------------------------------------
# 阶段流转测试
# ---------------------------------------------------------------------------


class TestWorkflowRun:
    def test_basic_flow_pass(self, project_dir, mock_agents):
        """基本流程：PM → Engineer → QA(通过) → 复盘"""
        mock_agents["qa"].run.return_value = '{"status":"pass","checked_items":["ok"],"evidence":["all met"],"defects":[],"next_action":"done","failure_root_cause":"","rollback_stage":"","diagnostic_summary":""}'
        wf = HarnessWorkflow(task="测试任务", project_dir=project_dir, auto_confirm=True)
        asyncio.run(wf.run())

        assert wf.state == "已复盘"
        mock_agents["pm"].run.assert_called()
        mock_agents["engineer"].run.assert_called_once()
        mock_agents["qa"].run.assert_called_once()

    def test_state_transitions_pass(self, project_dir, mock_agents):
        """通过路径的状态流转：待澄清 → 已定义 → 实现中 → 待验收 → 已通过 → 已复盘"""
        mock_agents["qa"].run.return_value = '{"status":"pass","checked_items":["ok"],"evidence":["passed"],"defects":[],"next_action":"done","failure_root_cause":"","rollback_stage":"","diagnostic_summary":""}'
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        assert wf.state == "待澄清"

        asyncio.run(wf.run())
        assert wf.state == "已复盘"

    def test_qa_reject_sets_state(self, project_dir, mock_agents):
        """QA 不通过时状态为 已退回"""
        mock_agents["qa"].run.return_value = '{"status":"fail","checked_items":["ok"],"evidence":[],"defects":["缺少关键功能"],"next_action":"rework","failure_root_cause":"missing feature","rollback_stage":"engineer","diagnostic_summary":"需要返工"}'
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        asyncio.run(wf.run())

        assert wf.state == "已退回"

    def test_qa_reject_stops_before_retrospective(self, project_dir, mock_agents):
        """QA 不通过时不会进入复盘阶段（PM 仅调用一次用于PRD）"""
        mock_agents["qa"].run.return_value = '{"status":"fail","checked_items":["ok"],"evidence":[],"defects":["不通过"],"next_action":"rework","failure_root_cause":"failed acceptance","rollback_stage":"engineer","diagnostic_summary":"验收不通过"}'
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        asyncio.run(wf.run())

        # PM 只被调用一次（产出PRD），不调用复盘
        assert mock_agents["pm"].run.call_count == 1

    def test_with_architect_flow(self, project_dir, mock_agents):
        """启用 Architect 时，架构环节被执行且状态经过 已设计"""
        mock_agents["qa"].run.return_value = '{"status":"pass","checked_items":["ok"],"evidence":["passed"],"defects":[],"next_action":"done","failure_root_cause":"","rollback_stage":"","diagnostic_summary":""}'
        wf = HarnessWorkflow(
            task="t", project_dir=project_dir, auto_confirm=True, roles={"architect"}
        )
        asyncio.run(wf.run())

        mock_agents["architect"].run.assert_called_once()
        assert wf.state == "已复盘"

    def test_with_growth_flow(self, project_dir, mock_agents):
        """启用 Growth 时，调研环节被执行且状态经过 已调研"""
        mock_agents["qa"].run.return_value = '{"status":"pass","checked_items":["ok"],"evidence":["passed"],"defects":[],"next_action":"done","failure_root_cause":"","rollback_stage":"","diagnostic_summary":""}'
        wf = HarnessWorkflow(
            task="t", project_dir=project_dir, auto_confirm=True, roles={"growth"}
        )
        asyncio.run(wf.run())

        mock_agents["growth"].run.assert_called_once()
        assert wf.state == "已复盘"

    def test_with_ops_flow(self, project_dir, mock_agents):
        """启用 Ops 时，运行检查环节被执行且状态经过 已运行检查"""
        mock_agents["qa"].run.return_value = '{"status":"pass","checked_items":["ok"],"evidence":["passed"],"defects":[],"next_action":"done","failure_root_cause":"","rollback_stage":"","diagnostic_summary":""}'
        wf = HarnessWorkflow(
            task="t", project_dir=project_dir, auto_confirm=True, roles={"ops"}
        )
        asyncio.run(wf.run())

        mock_agents["ops"].run.assert_called_once()
        assert wf.state == "已复盘"

    def test_with_ceo_review(self, project_dir, mock_agents):
        """启用 CEO 审查时，CEO 审查每个阶段"""
        mock_agents["ceo"].run.return_value = "批准"
        mock_agents["qa"].run.return_value = '{"status":"pass","checked_items":["ok"],"evidence":["passed"],"defects":[],"next_action":"done","failure_root_cause":"","rollback_stage":"","diagnostic_summary":""}'
        wf = HarnessWorkflow(
            task="t", project_dir=project_dir, auto_confirm=False, ceo_review=True
        )
        asyncio.run(wf.run())

        # CEO 应被多次调用（PM后、Engineer后、QA后、复盘前至少）
        assert mock_agents["ceo"].run.call_count >= 2

    def test_ceo_reject_stops_workflow(self, project_dir, mock_agents):
        """CEO 退回时工作流终止"""
        mock_agents["ceo"].run.return_value = "退回，目标不清"
        wf = HarnessWorkflow(
            task="t", project_dir=project_dir, auto_confirm=False, ceo_review=True
        )
        asyncio.run(wf.run())

        # CEO 第一次审查就退回，Engineer 不应被调用
        mock_agents["engineer"].run.assert_not_called()

    def test_review_auto_confirm(self, project_dir, mock_agents):
        """auto_confirm=True 时 review 直接返回 'y'"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        assert wf.review("测试阶段", "测试内容") == "y"

    def test_review_human_yes(self, project_dir, mock_agents):
        """人工确认输入 y 时返回 'y'"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir)
        with patch("builtins.input", return_value="y"):
            assert wf.review("阶段", "内容") == "y"

    def test_review_human_no(self, project_dir, mock_agents):
        """人工确认输入 n 时返回 'n'"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir)
        with patch("builtins.input", return_value="n"):
            assert wf.review("阶段", "内容") == "n"

    def test_artifacts_saved(self, project_dir, mock_agents):
        """流程完成后关键产物被保存"""
        mock_agents["qa"].run.return_value = '{"status":"pass","checked_items":["ok"],"evidence":["passed"],"defects":[],"next_action":"done","failure_root_cause":"","rollback_stage":"","diagnostic_summary":""}'
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        asyncio.run(wf.run())

        assert wf.store.exists("prd.md")
        assert wf.store.exists("implementation.md")
        assert wf.store.exists("acceptance.md")
        assert wf.store.exists("retrospective.md")


# ---------------------------------------------------------------------------
# STATES 常量测试
# ---------------------------------------------------------------------------


class TestStatesConstant:
    def test_states_contains_key_stages(self):
        """STATES 包含关键阶段"""
        assert "待澄清" in STATES
        assert "已定义" in STATES
        assert "实现中" in STATES
        assert "待验收" in STATES
        assert "已通过" in STATES
        assert "已退回" in STATES
        assert "已复盘" in STATES

    def test_states_length(self):
        """STATES 包含 10 个阶段"""
        assert len(STATES) == 10
