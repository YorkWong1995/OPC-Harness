"""测试中断恢复入口"""

import json
from pathlib import Path
import pytest

from opc.workflow import WorkflowState


def test_resume_loads_saved_state(tmp_path):
    """测试从持久化状态文件恢复 WorkflowState"""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    state_data = {
        "current_stage": "实现中",
        "completed_stages": ["已调研", "已定义", "已设计"],
        "artifact_paths": {"prd": str(artifacts_dir / "prd.md")},
        "task_description": "实现用户登录功能",
        "run_id": "abc123",
        "rework_attempts": 0,
        "stage_logs": {},
    }
    state_path = artifacts_dir / ".opc_state.json"
    state_path.write_text(json.dumps(state_data, ensure_ascii=False), encoding="utf-8")

    loaded = WorkflowState.load_state(artifacts_dir)
    assert loaded.current_stage == "实现中"
    assert loaded.completed_stages == ["已调研", "已定义", "已设计"]
    assert loaded.task_description == "实现用户登录功能"
    assert loaded.run_id == "abc123"


def test_resume_missing_state_file(tmp_path):
    """测试状态文件不存在时抛出异常"""
    with pytest.raises(FileNotFoundError):
        WorkflowState.load_state(tmp_path)


def test_resume_invalid_json(tmp_path):
    """测试状态文件内容非法时抛出异常"""
    state_path = tmp_path / ".opc_state.json"
    state_path.write_text("not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        WorkflowState.load_state(tmp_path)
