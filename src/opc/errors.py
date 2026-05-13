"""统一错误类型定义"""

from enum import Enum


class FailureType(str, Enum):
    """工作流中不同类型的失败"""
    API_FAILURE = "api_failure"
    TOOL_FAILURE = "tool_failure"
    ROLE_FAILURE = "role_failure"
    PROTOCOL_FAILURE = "protocol_failure"
    QA_FAILURE = "qa_failure"


class RetryPolicy(str, Enum):
    """重试策略"""
    RETRYABLE = "retryable"
    NOT_RETRYABLE = "not_retryable"
    HUMAN_INTERVENTION = "human_intervention"


# 失败类型 -> 默认重试策略
FAILURE_RETRY_POLICY: dict[FailureType, RetryPolicy] = {
    FailureType.API_FAILURE: RetryPolicy.RETRYABLE,
    FailureType.TOOL_FAILURE: RetryPolicy.RETRYABLE,
    FailureType.ROLE_FAILURE: RetryPolicy.NOT_RETRYABLE,
    FailureType.PROTOCOL_FAILURE: RetryPolicy.NOT_RETRYABLE,
    FailureType.QA_FAILURE: RetryPolicy.RETRYABLE,
}


class WorkflowError(Exception):
    """工作流错误基类"""

    def __init__(self, message: str, failure_type: FailureType, details: dict | None = None):
        super().__init__(message)
        self.failure_type = failure_type
        self.retry_policy = FAILURE_RETRY_POLICY[failure_type]
        self.details = details or {}


class APIFailure(WorkflowError):
    """API 调用失败（超时、限流、服务不可用）"""

    def __init__(self, message: str, status_code: int | None = None, **details):
        super().__init__(message, FailureType.API_FAILURE, {"status_code": status_code, **details})


class ToolFailure(WorkflowError):
    """工具执行失败（命令错误、文件不存在、权限不足）"""

    def __init__(self, message: str, tool_name: str, **details):
        super().__init__(message, FailureType.TOOL_FAILURE, {"tool_name": tool_name, **details})


class RoleFailure(WorkflowError):
    """角色执行失败（无法完成任务、输出不完整）"""

    def __init__(self, message: str, role: str, **details):
        super().__init__(message, FailureType.ROLE_FAILURE, {"role": role, **details})


class ProtocolFailure(WorkflowError):
    """协议失败（输出不符合 schema、路由到不存在角色）"""

    def __init__(self, message: str, **details):
        super().__init__(message, FailureType.PROTOCOL_FAILURE, details)


class QAFailure(WorkflowError):
    """QA 验收失败（测试不通过、质量不达标）"""

    def __init__(self, message: str, defects: list[str] | None = None, **details):
        super().__init__(message, FailureType.QA_FAILURE, {"defects": defects or [], **details})
