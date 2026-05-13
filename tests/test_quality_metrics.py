"""测试工作流质量指标"""

import json
from pathlib import Path

from src.opc.workflow import WorkflowState, generate_metrics


def test_quality_metrics_qa_passed(tmp_path):
    """QA 通过时质量指标正确"""
    state = WorkflowState(
        task_description="test task",
        current_stage="已通过",
        rework_attempts=1,
        stage_logs={
            "pm": {"input_tokens": 100, "output_tokens": 50, "duration_seconds": 1.0, "tool_calls": 0, "api_calls": 1},
            "engineer": {"input_tokens": 200, "output_tokens": 100, "duration_seconds": 2.0, "tool_calls": 3, "api_calls": 2},
        },
    )

    metrics_path = generate_metrics(state, tmp_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert metrics["quality"]["qa_passed"] is True
    assert metrics["quality"]["rework_attempts"] == 1
    assert metrics["quality"]["human_interventions"] == 0
    assert metrics["totals"]["input_tokens"] == 300
    assert metrics["totals"]["tool_calls"] == 3


def test_quality_metrics_qa_failed(tmp_path):
    """QA 未通过时质量指标正确"""
    state = WorkflowState(
        task_description="test task",
        current_stage="已退回",
        rework_attempts=2,
        stage_logs={
            "_human_interventions": 1,
            "_failure_types": {"qa_failure": 2, "tool_failure": 1},
            "pm": {"input_tokens": 100, "output_tokens": 50, "duration_seconds": 1.0, "tool_calls": 0, "api_calls": 1},
        },
    )

    metrics_path = generate_metrics(state, tmp_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert metrics["quality"]["qa_passed"] is False
    assert metrics["quality"]["rework_attempts"] == 2
    assert metrics["quality"]["human_interventions"] == 1
    assert metrics["quality"]["failure_types"] == {"qa_failure": 2, "tool_failure": 1}
    # 内部字段不出现在 stages 中
    assert "_human_interventions" not in metrics["stages"]
    assert "_failure_types" not in metrics["stages"]
