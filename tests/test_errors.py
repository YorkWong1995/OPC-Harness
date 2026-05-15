"""测试统一错误类型"""

from opc.errors import (
    FailureType, RetryPolicy, WorkflowError,
    APIFailure, ToolFailure, RoleFailure, ProtocolFailure, QAFailure,
    FAILURE_RETRY_POLICY,
)


def test_failure_types_complete():
    """所有失败类型都有对应的重试策略"""
    for ft in FailureType:
        assert ft in FAILURE_RETRY_POLICY


def test_api_failure():
    err = APIFailure("timeout", status_code=503)
    assert err.failure_type == FailureType.API_FAILURE
    assert err.retry_policy == RetryPolicy.RETRYABLE
    assert err.details["status_code"] == 503


def test_tool_failure():
    err = ToolFailure("file not found", tool_name="read_file")
    assert err.failure_type == FailureType.TOOL_FAILURE
    assert err.retry_policy == RetryPolicy.RETRYABLE
    assert err.details["tool_name"] == "read_file"


def test_role_failure():
    err = RoleFailure("cannot complete", role="engineer")
    assert err.failure_type == FailureType.ROLE_FAILURE
    assert err.retry_policy == RetryPolicy.NOT_RETRYABLE


def test_protocol_failure():
    err = ProtocolFailure("invalid schema", field="acceptance_criteria")
    assert err.failure_type == FailureType.PROTOCOL_FAILURE
    assert err.retry_policy == RetryPolicy.NOT_RETRYABLE
    assert err.details["field"] == "acceptance_criteria"


def test_qa_failure():
    err = QAFailure("tests failed", defects=["login broken", "css issue"])
    assert err.failure_type == FailureType.QA_FAILURE
    assert err.retry_policy == RetryPolicy.RETRYABLE
    assert len(err.details["defects"]) == 2


def test_workflow_error_is_exception():
    err = APIFailure("test")
    assert isinstance(err, Exception)
    assert isinstance(err, WorkflowError)
    assert str(err) == "test"
