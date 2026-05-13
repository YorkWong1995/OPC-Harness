"""最小声明式 workflow spec

P3 只实现最小声明式 spec，用于表达 QA.pass → Done 和 QA.fail → Engineer。
不做完整 workflow 引擎，不做 roles/steps/retry/approval 的完整抽象。

设计原则：
- MVP 阶段核心工作流保持同步执行
- 异步只用于测试、构建、索引等长耗时工具任务
- 核心角色主链路（PM → Engineer → QA）保持同步
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Transition:
    """状态流转规则"""
    from_state: str
    condition: str  # "pass", "fail", "timeout", "error"
    to_state: str


@dataclass
class WorkflowSpec:
    """最小声明式工作流规范

    P3 只支持线性流转和 QA 退回，不支持并行分支或条件路由。
    """
    name: str = "default"
    states: list[str] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    initial_state: str = ""
    terminal_states: list[str] = field(default_factory=list)

    def next_state(self, current: str, condition: str) -> str | None:
        """根据当前状态和条件查找下一个状态"""
        for t in self.transitions:
            if t.from_state == current and t.condition == condition:
                return t.to_state
        return None

    def is_terminal(self, state: str) -> bool:
        return state in self.terminal_states


# 默认 MVP 工作流 spec
DEFAULT_WORKFLOW_SPEC = WorkflowSpec(
    name="mvp_pm_engineer_qa",
    states=["待澄清", "已定义", "实现中", "待验收", "已通过", "已退回", "已复盘"],
    transitions=[
        Transition("待澄清", "pass", "已定义"),
        Transition("已定义", "pass", "实现中"),
        Transition("实现中", "pass", "待验收"),
        Transition("待验收", "pass", "已通过"),
        Transition("待验收", "fail", "已退回"),
        Transition("已退回", "pass", "实现中"),
        Transition("已通过", "pass", "已复盘"),
    ],
    initial_state="待澄清",
    terminal_states=["已复盘"],
)


@dataclass
class AsyncToolTask:
    """异步工具任务（用于长耗时操作）

    设计规则：
    - 顺序：同一 stage 内的异步任务按提交顺序完成
    - 幂等：相同参数的重复提交返回已有结果
    - 超时：超过 timeout 后标记为 failed
    - 取消：支持通过 cancel() 取消未完成的任务
    """
    task_id: str
    tool_name: str
    inputs: dict = field(default_factory=dict)
    timeout_seconds: int = 300
    status: str = "pending"  # pending, running, completed, failed, cancelled
    result: str | None = None
    error: str | None = None


# 并行任务和子工作流预留接口
class SubWorkflow:
    """子工作流接口（Planned，P3 不实现）

    预留用于：
    - 并行执行多个独立子任务
    - 嵌套工作流（如 Engineer 内部的 code → test → lint 子流程）
    - 条件分支（根据任务类型选择不同子流程）
    """

    def __init__(self, spec: WorkflowSpec):
        self.spec = spec

    async def run(self, context: dict) -> dict:
        raise NotImplementedError("SubWorkflow 在 P3 中未实现")
