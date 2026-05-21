from opc.workflow_spec import (
    DEFAULT_WORKFLOW_SPEC,
    StageContract,
    StageResult,
    StageValidation,
    TransitionPolicy,
    validate_stage_contract,
)


def test_default_stage_contracts_cover_core_dag_fields():
    contracts = DEFAULT_WORKFLOW_SPEC.stage_contracts()

    for stage in ["pm", "engineer", "qa", "retro"]:
        contract = contracts[stage]
        assert contract.input_schema
        assert contract.role
        assert contract.output_schema
        assert contract.artifact
        assert contract.transition.on_pass

    assert contracts["qa"].conditional_branches["rework"] == "已退回"
    assert contracts["engineer"].failure_branch == "已退回"
    assert contracts["architect"].parallel_group == "growth_architect"


def test_stage_contract_validation_rejects_missing_fields():
    contract = StageContract(
        name="",
        role="pm",
        input_schema="ContextPack",
        output_schema="PMOutput",
        artifact="pm_prd",
    )

    validation = validate_stage_contract(contract, set(DEFAULT_WORKFLOW_SPEC.states))

    assert validation.status == "failed"
    assert "name" in validation.missing_fields


def test_stage_contract_validation_rejects_schema_mismatch():
    contract = StageContract(
        name="pm",
        role="pm",
        input_schema="",
        output_schema="",
        artifact="pm_prd",
    )

    validation = validate_stage_contract(contract, set(DEFAULT_WORKFLOW_SPEC.states))

    assert validation.status == "failed"
    assert "input_schema" in validation.missing_fields
    assert "output_schema" in validation.missing_fields


def test_stage_contract_validation_rejects_illegal_transition():
    contract = StageContract(
        name="qa",
        role="qa",
        input_schema="ContextPack",
        output_schema="QAOutput",
        artifact="qa_report",
        transition=TransitionPolicy(on_pass="不存在的状态"),
    )

    validation = validate_stage_contract(contract, set(DEFAULT_WORKFLOW_SPEC.states))

    assert validation.status == "failed"
    assert "illegal transition target: 不存在的状态" in validation.schema_errors


def test_stage_result_records_failure_branch_validation():
    validation = StageValidation(
        status="failed",
        reason="QA requested rework",
        schema_errors=["next_action=rework"],
    )
    result = StageResult(
        stage="qa",
        status="failed",
        validation=validation,
        next_state="已退回",
        failure_reason="defects found",
    )

    assert not result.validation.passed
    assert result.next_state == "已退回"
    assert result.failure_reason == "defects found"
