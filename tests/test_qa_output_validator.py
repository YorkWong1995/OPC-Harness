"""测试 P2.3 QAOutput 跨字段一致性校验。"""

import pytest
from pydantic import ValidationError

from opc.schema import QAOutput


def test_qa_output_pass_with_done_is_valid():
    """status=pass + next_action=done 是合法组合。"""
    qa = QAOutput(status="pass", next_action="done")
    assert qa.status == "pass"
    assert qa.next_action == "done"


def test_qa_output_fail_with_rework_is_valid():
    """status=fail + next_action=rework 是合法组合。"""
    qa = QAOutput(status="fail", next_action="rework", defects=["缺陷 X"])
    assert qa.status == "fail"
    assert qa.next_action == "rework"


def test_qa_output_pass_with_rework_is_invalid():
    """status=pass + next_action=rework 是矛盾组合，应拒绝。"""
    with pytest.raises(ValidationError, match="status=pass 不能与 next_action=rework 同时出现"):
        QAOutput(status="pass", next_action="rework")


def test_qa_output_fail_with_done_is_invalid():
    """status=fail + next_action=done 是矛盾组合，应拒绝。"""
    with pytest.raises(ValidationError, match="status=fail 不能与 next_action=done 同时出现"):
        QAOutput(status="fail", next_action="done")


def test_qa_output_fail_with_human_intervention_is_valid():
    """status=fail + next_action=human_intervention 是合法组合。"""
    qa = QAOutput(status="fail", next_action="human_intervention", defects=["需人工介入"])
    assert qa.status == "fail"
    assert qa.next_action == "human_intervention"
