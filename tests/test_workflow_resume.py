"""测试 WorkflowState 状态保存和恢复逻辑"""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opc.workflow import HarnessWorkflow, WorkflowState, STATES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def artifacts_dir(tmp_path):
    """临时 artifacts 目录"""
    d = tmp_path / "artifacts"
    d.mkdir()
    return d


@pytest.fixture
def project_dir(tmp_path):
    """临时项目目录"""
    return tmp_path


import json as _json

_VALID_PM_OUTPUT = _json.dumps({
    "background": "模拟背景",
    "goal": "模拟目标",
    "scope": ["scope1"],
    "acceptance_criteria": ["ac1"],
}, ensure_ascii=False)

_VALID_ENGINEER_OUTPUT = _json.dumps({
    "changed_files": ["src/main.py"],
    "implementation_summary": "模拟实现完成",
    "test_result": "passed",
}, ensure_ascii=False)

_VALID_QA_PASS_OUTPUT = _json.dumps({
    "status": "pass",
    "checked_items": ["功能测试"],
    "evidence": ["测试通过"],
    "next_action": "done",
}, ensure_ascii=False)


def _make_agent_mock(return_value="模拟输出"):
    agent = MagicMock()
    agent.run.return_value = return_value
    return agent


@pytest.fixture
def mock_agents():
    """统一 mock 所有 create_*_agent 工厂函数"""
    mocks = {
        "pm": _make_agent_mock(_VALID_PM_OUTPUT),
        "engineer": _make_agent_mock(_VALID_ENGINEER_OUTPUT),
        "qa": _make_agent_mock(_VALID_QA_PASS_OUTPUT),
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
# WorkflowState 数据类测试
# ---------------------------------------------------------------------------


class TestWorkflowState:
    def test_default_values(self):
        """默认状态字段正确"""
        state = WorkflowState()
        assert state.current_stage == "待澄清"
        assert state.completed_stages == []
        assert state.artifact_paths == {}
        assert state.task_description == ""

    def test_custom_values(self):
        """自定义字段正确存储"""
        state = WorkflowState(
            current_stage="已定义",
            completed_stages=["待澄清", "已定义"],
            artifact_paths={"prd": "/tmp/prd.md"},
            task_description="测试任务",
        )
        assert state.current_stage == "已定义"
        assert state.completed_stages == ["待澄清", "已定义"]
        assert state.artifact_paths == {"prd": "/tmp/prd.md"}
        assert state.task_description == "测试任务"


# ---------------------------------------------------------------------------
# save_state 测试
# ---------------------------------------------------------------------------


class TestSaveState:
    def test_save_creates_file(self, project_dir, mock_agents):
        """save_state 创建 .opc_state.json 文件"""
        wf = HarnessWorkflow(task="测试任务", project_dir=project_dir, auto_confirm=True)
        wf.save_state()

        state_path = project_dir / "artifacts" / ".opc_state.json"
        assert state_path.exists()

    def test_save_content_valid_json(self, project_dir, mock_agents):
        """save_state 写入合法 JSON"""
        wf = HarnessWorkflow(task="测试任务", project_dir=project_dir, auto_confirm=True)
        wf.state = "已定义"
        wf.save_state()

        state_path = project_dir / "artifacts" / ".opc_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_save_reflects_current_state(self, project_dir, mock_agents):
        """save_state 保存当前 state 到 current_stage"""
        wf = HarnessWorkflow(task="测试任务", project_dir=project_dir, auto_confirm=True)
        wf.state = "实现中"
        wf.save_state()

        state_path = project_dir / "artifacts" / ".opc_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["current_stage"] == "实现中"

    def test_save_includes_task_description(self, project_dir, mock_agents):
        """save_state 包含 task_description"""
        wf = HarnessWorkflow(task="构建功能X", project_dir=project_dir, auto_confirm=True)
        wf.save_state()

        state_path = project_dir / "artifacts" / ".opc_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["task_description"] == "构建功能X"

    def test_save_includes_completed_stages(self, project_dir, mock_agents):
        """save_state 包含 completed_stages"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        wf.workflow_state.completed_stages = ["已定义", "实现中"]
        wf.state = "待验收"
        wf.save_state()

        state_path = project_dir / "artifacts" / ".opc_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["completed_stages"] == ["已定义", "实现中"]

    def test_save_includes_artifact_paths(self, project_dir, mock_agents):
        """save_state 包含 artifact_paths"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        wf.workflow_state.artifact_paths = {"prd": "/tmp/prd.md"}
        wf.save_state()

        state_path = project_dir / "artifacts" / ".opc_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["artifact_paths"] == {"prd": "/tmp/prd.md"}

    def test_save_overwrites_previous(self, project_dir, mock_agents):
        """多次 save_state 覆盖之前的文件"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        wf.state = "已定义"
        wf.save_state()
        wf.state = "实现中"
        wf.save_state()

        state_path = project_dir / "artifacts" / ".opc_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["current_stage"] == "实现中"


# ---------------------------------------------------------------------------
# load_state 测试
# ---------------------------------------------------------------------------


class TestLoadState:
    def test_load_from_file(self, artifacts_dir):
        """load_state 从 JSON 文件恢复 WorkflowState"""
        state_data = {
            "current_stage": "实现中",
            "completed_stages": ["已定义"],
            "artifact_paths": {"prd": "/tmp/prd.md"},
            "task_description": "恢复任务",
        }
        state_path = artifacts_dir / ".opc_state.json"
        state_path.write_text(json.dumps(state_data, ensure_ascii=False), encoding="utf-8")

        loaded = WorkflowState.load_state(artifacts_dir)
        assert loaded.current_stage == "实现中"
        assert loaded.completed_stages == ["已定义"]
        assert loaded.artifact_paths == {"prd": "/tmp/prd.md"}
        assert loaded.task_description == "恢复任务"

    def test_load_file_not_found(self, artifacts_dir):
        """状态文件不存在时抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            WorkflowState.load_state(artifacts_dir)

    def test_load_invalid_json(self, artifacts_dir):
        """状态文件内容非法 JSON 时抛出 JSONDecodeError"""
        state_path = artifacts_dir / ".opc_state.json"
        state_path.write_text("not valid json {{{", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            WorkflowState.load_state(artifacts_dir)

    def test_load_roundtrip(self, project_dir, mock_agents):
        """save → load 往返一致性"""
        wf = HarnessWorkflow(task="往返测试", project_dir=project_dir, auto_confirm=True)
        wf.state = "待验收"
        wf.workflow_state.completed_stages = ["已定义", "实现中"]
        wf.workflow_state.artifact_paths = {"prd": "artifacts/prd.md", "implementation": "artifacts/impl.md"}
        wf.save_state()

        loaded = WorkflowState.load_state(wf.store.dir)
        assert loaded.current_stage == "待验收"
        assert loaded.completed_stages == ["已定义", "实现中"]
        assert loaded.artifact_paths == {"prd": "artifacts/prd.md", "implementation": "artifacts/impl.md"}
        assert loaded.task_description == "往返测试"


# ---------------------------------------------------------------------------
# resume_from 恢复流程测试
# ---------------------------------------------------------------------------


class TestResumeFrom:
    def test_invalid_stage_raises(self, project_dir, mock_agents):
        """无效阶段名抛出 ValueError"""
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        with pytest.raises(ValueError, match="无效的阶段名"):
            asyncio.run(wf.run(resume_from="不存在的阶段"))

    def test_resume_skips_completed_stages(self, project_dir, mock_agents):
        """resume_from 跳过已完成阶段"""
        mock_agents["qa"].run.return_value = _VALID_QA_PASS_OUTPUT

        # 先正常运行到 "已定义" 阶段并保存状态
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        wf.state = "已定义"
        wf.workflow_state.completed_stages = ["已定义"]
        wf.workflow_state.artifact_paths = {"prd": str(wf.store.dir / "prd.md")}
        # 写入 prd 产物
        wf.store.save("prd.md", "模拟PRD内容")
        wf.save_state()

        # 创建新 workflow 并 resume
        wf2 = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        asyncio.run(wf2.run(resume_from="实现中"))

        # PRD 阶段被跳过：prd.md 内容应保留原始内容（不被 PM 重新生成覆盖）
        prd_content = (wf2.store.dir / "prd.md").read_text(encoding="utf-8")
        assert prd_content == "模拟PRD内容"
        # Engineer 应被调用
        mock_agents["engineer"].run.assert_called_once()

    def test_resume_loads_state_from_file(self, project_dir, mock_agents):
        """resume_from 从文件加载状态"""
        mock_agents["qa"].run.return_value = _VALID_QA_PASS_OUTPUT

        # 手动写入状态文件
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        prd_path = artifacts_dir / "prd.md"
        prd_path.write_text("已有PRD", encoding="utf-8")

        state_data = {
            "current_stage": "已定义",
            "completed_stages": ["已定义"],
            "artifact_paths": {"prd": str(prd_path)},
            "task_description": "t",
        }
        state_path = artifacts_dir / ".opc_state.json"
        state_path.write_text(json.dumps(state_data, ensure_ascii=False), encoding="utf-8")

        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        asyncio.run(wf.run(resume_from="实现中"))

        # 验证状态被正确恢复
        assert "已定义" in wf.workflow_state.completed_stages

    def test_resume_full_flow_completes(self, project_dir, mock_agents):
        """从中间阶段恢复后能完成整个流程"""
        mock_agents["qa"].run.return_value = _VALID_QA_PASS_OUTPUT

        # 准备已完成到 "实现中" 的状态
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        prd_path = artifacts_dir / "prd.md"
        prd_path.write_text("模拟PRD", encoding="utf-8")
        impl_path = artifacts_dir / "implementation.md"
        impl_path.write_text("模拟实现", encoding="utf-8")

        state_data = {
            "current_stage": "实现中",
            "completed_stages": ["已定义", "实现中"],
            "artifact_paths": {
                "prd": str(prd_path),
                "implementation": str(impl_path),
            },
            "task_description": "t",
        }
        state_path = artifacts_dir / ".opc_state.json"
        state_path.write_text(json.dumps(state_data, ensure_ascii=False), encoding="utf-8")

        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        asyncio.run(wf.run(resume_from="待验收"))

        assert wf.state == "已复盘"
        # QA 应被调用
        mock_agents["qa"].run.assert_called_once()

    def test_save_state_called_during_run(self, project_dir, mock_agents):
        """正常 run 过程中每个阶段完成后都会调用 save_state"""
        mock_agents["qa"].run.return_value = _VALID_QA_PASS_OUTPUT
        wf = HarnessWorkflow(task="t", project_dir=project_dir, auto_confirm=True)
        asyncio.run(wf.run())

        # 验证状态文件存在且最终状态正确
        state_path = project_dir / "artifacts" / ".opc_state.json"
        assert state_path.exists()
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["current_stage"] == "已复盘"
        assert "已定义" in data["completed_stages"]
        assert "实现中" in data["completed_stages"]
        assert "待验收" in data["completed_stages"]
        assert "已通过" in data["completed_stages"]
        assert "已复盘" in data["completed_stages"]
