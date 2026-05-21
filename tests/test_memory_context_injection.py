from unittest.mock import MagicMock, patch

from opc.memory import MemoryRecord
from opc.workflow import HarnessWorkflow


def _workflow(tmp_path):
    with (
        patch("opc.workflow.create_pm_agent", return_value=MagicMock()),
        patch("opc.workflow.create_engineer_agent", return_value=MagicMock()),
        patch("opc.workflow.create_embedded_engineer_agent", return_value=MagicMock()),
        patch("opc.workflow.create_qa_agent", return_value=MagicMock()),
    ):
        return HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True, roles=set())


def test_context_pack_injects_selected_memory_with_sources(tmp_path):
    workflow = _workflow(tmp_path)
    workflow.memory_records = [
        MemoryRecord(content="优先使用本地 trace", scope="user", source="manual"),
        MemoryRecord(content="临时 run 状态", scope="run", source="run_trace"),
    ]

    pack = workflow._build_context_pack("engineer", "实现中")

    assert "memory.user: 优先使用本地 trace" in pack.facts
    assert "memory.run: 临时 run 状态" not in pack.facts
    memory_sources = [source for source in pack.context_sources if source.get("type") == "memory"]
    assert memory_sources == [
        {
            "type": "memory",
            "name": "memory:0",
            "scope": "user",
            "source": "manual",
            "role": "engineer",
            "status": "selected",
            "reason": "scope_role_match",
        }
    ]


def test_context_pack_memory_conflict_prefers_current_fact(tmp_path):
    workflow = _workflow(tmp_path)
    summary = workflow._create_stage_summary(stage="pm", goal="当前事实")
    workflow._record_stage_summary("pm", summary)
    workflow.memory_records = [MemoryRecord(content="pm.goal: 当前事实", scope="project", source="old-memory")]

    pack = workflow._build_context_pack("engineer", "实现中")

    assert "memory.project: pm.goal: 当前事实" not in pack.facts
    assert any(
        source.get("type") == "memory" and source.get("status") == "conflict_current_fact"
        for source in pack.context_sources
    )
