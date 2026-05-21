import pytest

from opc.workflow_spec import DEFAULT_WORKFLOW_SPEC, StageResult, StageValidation


GOLDEN_CASES = [
    {
        "case": "bugfix",
        "stage": "qa",
        "expected_output_schema": "QAOutput",
        "expected_transition": "已通过",
        "failure_branch": "已退回",
        "failure判定": "缺少测试证据或 QA fail 后不回退",
    },
    {
        "case": "review",
        "stage": "qa",
        "expected_output_schema": "QAOutput",
        "expected_transition": "已通过",
        "failure_branch": "已退回",
        "failure判定": "发生写入或无阻塞/非阻塞分类",
    },
    {
        "case": "docs-update",
        "stage": "engineer",
        "expected_output_schema": "EngineerOutput",
        "expected_transition": "实现中",
        "failure_branch": "已退回",
        "failure判定": "链接漂移仍存在或无检查证据",
    },
    {
        "case": "config-drift",
        "stage": "engineer",
        "expected_output_schema": "EngineerOutput",
        "expected_transition": "实现中",
        "failure_branch": "已退回",
        "failure判定": "无效配置未被发现或诊断不可读",
    },
    {
        "case": "failed-tool",
        "stage": "engineer",
        "expected_output_schema": "EngineerOutput",
        "expected_transition": "实现中",
        "failure_branch": "已退回",
        "failure判定": "危险动作继续执行或无结构化原因",
    },
    {
        "case": "rework-resume",
        "stage": "qa",
        "expected_output_schema": "QAOutput",
        "expected_transition": "已通过",
        "failure_branch": "已退回",
        "failure判定": "resume 丢失 defects、acceptance 或 artifact",
    },
]


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[item["case"] for item in GOLDEN_CASES])
def test_stage_contract_golden_cases_match_default_contracts(case):
    contracts = DEFAULT_WORKFLOW_SPEC.stage_contracts()
    contract = contracts[case["stage"]]

    assert contract.output_schema == case["expected_output_schema"]
    assert contract.transition.on_pass == case["expected_transition"]
    assert (contract.failure_branch or contract.transition.on_fail) == case["failure_branch"]
    assert case["failure判定"]


def test_stage_contract_golden_failure_result_shape():
    result = StageResult(
        stage="engineer",
        status="failed",
        validation=StageValidation("failed", reason="tool denied", schema_errors=["guardrail_blocked"]),
        next_state="已退回",
        failure_reason="dangerous command denied",
    )

    assert result.status == "failed"
    assert result.validation.status == "failed"
    assert result.next_state == "已退回"
    assert "dangerous" in result.failure_reason


def test_stage_contract_golden_cases_document_all_required_sections():
    assert {case["case"] for case in GOLDEN_CASES} == {
        "bugfix",
        "review",
        "docs-update",
        "config-drift",
        "failed-tool",
        "rework-resume",
    }
    for case in GOLDEN_CASES:
        assert case["expected_output_schema"]
        assert case["expected_transition"]
        assert case["failure_branch"]
        assert case["failure判定"]
