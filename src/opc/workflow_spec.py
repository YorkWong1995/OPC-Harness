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
from pathlib import Path
import re
from typing import Any, Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


@dataclass
class WorkflowStage:
    """声明式阶段定义。"""
    name: str
    state: str
    optional_role: str = ""
    parallel_group: str = ""
    approval_required: bool = True


ValidationStatus = Literal["passed", "failed", "skipped"]
TransitionCondition = Literal["pass", "fail", "timeout", "error", "approval_required", "human_intervention"]


@dataclass
class StageValidation:
    """阶段输入、输出或产物校验结果。"""
    status: ValidationStatus
    reason: str = ""
    missing_fields: list[str] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "passed"


@dataclass
class TransitionPolicy:
    """阶段结束后的状态流转策略。"""
    on_pass: str = ""
    on_fail: str = ""
    on_error: str = ""
    on_timeout: str = ""
    failure_branch: str = ""
    retry_limit: int = 0
    approval_required: bool = False

    def next_state(self, condition: str) -> str | None:
        mapping = {
            "pass": self.on_pass,
            "fail": self.on_fail,
            "error": self.on_error,
            "timeout": self.on_timeout,
        }
        return mapping.get(condition) or None


@dataclass
class StageResult:
    """阶段执行后的结构化结果。"""
    stage: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    validation: StageValidation = field(default_factory=lambda: StageValidation("skipped"))
    next_state: str = ""
    failure_reason: str = ""


@dataclass
class StageContract:
    """统一阶段执行契约，用于描述完整 DAG 阶段能力。"""
    name: str
    role: str
    input_schema: str
    output_schema: str
    artifact: str
    validation: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    transition: TransitionPolicy = field(default_factory=TransitionPolicy)
    conditional_branches: dict[str, str] = field(default_factory=dict)
    failure_branch: str = ""
    retry_policy: dict[str, int | str] = field(default_factory=dict)
    parallel_group: str = ""
    sub_workflow: str = ""


def validate_stage_contract(contract: StageContract, states: set[str]) -> StageValidation:
    missing: list[str] = []
    for field_name in ["name", "role", "input_schema", "output_schema", "artifact"]:
        if not getattr(contract, field_name):
            missing.append(field_name)
    transition_targets = [
        contract.transition.on_pass,
        contract.transition.on_fail,
        contract.transition.on_error,
        contract.transition.on_timeout,
        contract.transition.failure_branch,
        contract.failure_branch,
        *contract.conditional_branches.values(),
    ]
    illegal = [target for target in transition_targets if target and target not in states]
    if missing or illegal:
        errors = [f"illegal transition target: {target}" for target in illegal]
        return StageValidation("failed", "stage contract invalid", missing_fields=missing, schema_errors=errors)
    return StageValidation("passed")


@dataclass
class Transition:
    """状态流转规则"""
    from_state: str
    condition: str  # "pass", "fail", "timeout", "error"
    to_state: str


_ALLOWED_WORKFLOW_PACK_KINDS = {"claude_skill", "opc_runtime_workflow", "documentation"}
_ALLOWED_WORKFLOW_PACK_PERMISSIONS = {"read", "write", "execute", "model", "approval", "artifact", "trace", "git_diff", "run_tests", "run_lint", "run_typecheck"}
_REQUIRED_WORKFLOW_PACK_FIELDS = {"id", "kind", "owner_roles", "inputs", "outputs", "permissions", "acceptance", "trace"}


@dataclass(frozen=True)
class WorkflowPackManifest:
    id: str
    kind: str
    owner_roles: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    permissions: tuple[str, ...]
    acceptance: tuple[str, ...]
    trace: tuple[str, ...]
    stages: tuple[WorkflowStage, ...] = ()
    transitions: tuple[Transition, ...] = ()
    source_path: str = ""
    validation_errors: tuple[str, ...] = ()

    @property
    def runtime_executable(self) -> bool:
        return self.kind == "opc_runtime_workflow" and not self.validation_errors

    @property
    def disabled_reason(self) -> str:
        if self.validation_errors:
            return "; ".join(self.validation_errors)
        if self.kind != "opc_runtime_workflow":
            return f"kind={self.kind} is not runtime executable"
        if not self.stages:
            return "runtime stages are not declared; discovery/smoke only"
        return ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "owner_roles": list(self.owner_roles),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "permissions": list(self.permissions),
            "acceptance": list(self.acceptance),
            "trace": list(self.trace),
            "stages": [stage.__dict__ for stage in self.stages],
            "transitions": [transition.__dict__ for transition in self.transitions],
            "source_path": self.source_path,
            "runtime_executable": self.runtime_executable,
            "disabled_reason": self.disabled_reason,
        }


def workflow_pack_manifest_from_dict(data: dict[str, Any], *, source_path: str = "") -> WorkflowPackManifest:
    unknown = sorted(set(data) - (_REQUIRED_WORKFLOW_PACK_FIELDS | {"stages", "transitions"}))
    missing = sorted(field for field in _REQUIRED_WORKFLOW_PACK_FIELDS if field not in data)
    errors = [f"unknown field: {field}" for field in unknown] + [f"missing field: {field}" for field in missing]
    kind = str(data.get("kind", "")).strip()
    if kind and kind not in _ALLOWED_WORKFLOW_PACK_KINDS:
        errors.append(f"unknown kind: {kind}")
    permissions = _manifest_tuple(data.get("permissions", ()))
    for permission in permissions:
        if permission not in _ALLOWED_WORKFLOW_PACK_PERMISSIONS:
            errors.append(f"unknown permission: {permission}")
    stages = tuple(WorkflowStage(**stage) for stage in data.get("stages", ()) if isinstance(stage, dict))
    transitions = tuple(Transition(**transition) for transition in data.get("transitions", ()) if isinstance(transition, dict))
    states = {stage.state for stage in stages}
    for transition in transitions:
        if transition.from_state not in states or transition.to_state not in states:
            errors.append(f"illegal transition: {transition.from_state}->{transition.to_state}")
        if transition.condition not in {"pass", "fail", "timeout", "error", "approval_required", "human_intervention"}:
            errors.append(f"unknown transition condition: {transition.condition}")
    return WorkflowPackManifest(
        id=str(data.get("id", "")).strip(),
        kind=kind,
        owner_roles=_manifest_tuple(data.get("owner_roles", ())),
        inputs=_manifest_tuple(data.get("inputs", ())),
        outputs=_manifest_tuple(data.get("outputs", ())),
        permissions=permissions,
        acceptance=_manifest_tuple(data.get("acceptance", ())),
        trace=_manifest_tuple(data.get("trace", ())),
        stages=stages,
        transitions=transitions,
        source_path=source_path,
        validation_errors=tuple(errors),
    )


def discover_workflow_pack_manifests(project_root: Path) -> list[WorkflowPackManifest]:
    pack_dir = project_root / "docs" / "workflow-packs"
    if not pack_dir.exists():
        return []
    manifests: list[WorkflowPackManifest] = []
    for path in sorted(pack_dir.glob("*.md")):
        if path.name in {"README.md", "manifest-template.md"}:
            continue
        manifests.append(_workflow_pack_manifest_from_markdown(path))
    return manifests


def _workflow_pack_manifest_from_markdown(path: Path) -> WorkflowPackManifest:
    data: dict[str, Any] = {}
    in_manifest = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "## Manifest":
            in_manifest = True
            continue
        if in_manifest and stripped.startswith("## "):
            break
        if not in_manifest or not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "字段":
            continue
        key, value = cells[0], cells[1]
        if key == "permissions":
            data[key] = _permission_tokens_from_text(value)
        elif key in {"owner_roles", "inputs", "outputs", "acceptance", "trace"}:
            data[key] = tuple(part.strip(" `") for part in re.split(r"[,，、;/；]", value) if part.strip(" `"))
        else:
            data[key] = value.strip(" `")
    return workflow_pack_manifest_from_dict(data, source_path=str(path))


def _permission_tokens_from_text(value: str) -> tuple[str, ...]:
    tokens: list[str] = []
    if "只读" in value or "read" in value.lower():
        tokens.append("read")
    if "写" in value or "write" in value.lower():
        tokens.append("write")
    if "执行" in value or "命令" in value or "execute" in value.lower():
        tokens.append("execute")
    if "审批" in value or "确认" in value or "approval" in value.lower():
        tokens.append("approval")
    return tuple(dict.fromkeys(tokens or ["read"]))


def _manifest_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


@dataclass
class WorkflowSpec:
    """最小声明式工作流规范

    P3 只支持线性流转和 QA 退回，不支持并行分支或条件路由。
    """
    name: str = "default"
    states: list[str] = field(default_factory=list)
    stages: list[WorkflowStage] = field(default_factory=list)
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

    def stage_contracts(self) -> dict[str, StageContract]:
        """返回当前 spec 的阶段契约，供校验与文档生成使用。"""
        states = set(self.states)
        contracts = {
            contract.name: contract
            for contract in DEFAULT_STAGE_CONTRACTS
            if not states or validate_stage_contract(contract, states).passed
        }
        return contracts

    def runtime_stages(self, enabled_roles: set[str]) -> list[str]:
        """根据声明式阶段和已启用角色生成运行时阶段列表。"""
        stages: list[str] = []
        enabled_parallel_groups = {
            group
            for group in {stage.parallel_group for stage in self.stages if stage.parallel_group}
            if all(
                stage.optional_role in enabled_roles
                for stage in self.stages
                if stage.parallel_group == group and stage.optional_role
            )
        }
        for stage in self.stages:
            if stage.optional_role and stage.optional_role not in enabled_roles:
                continue
            if stage.parallel_group in enabled_parallel_groups:
                if stage.name == "architect" and stage.parallel_group not in stages:
                    stages.append(stage.parallel_group)
                continue
            stages.append(stage.name)
        return stages

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowSpec":
        stages = [WorkflowStage(**stage) for stage in data.get("stages", [])]
        transitions = [Transition(**transition) for transition in data.get("transitions", [])]
        return cls(
            name=str(data.get("name", "custom")),
            states=[str(state) for state in data.get("states", [])],
            stages=stages,
            transitions=transitions,
            initial_state=str(data.get("initial_state", "")),
            terminal_states=[str(state) for state in data.get("terminal_states", [])],
        )


def load_workflow_spec(project_dir: Path) -> WorkflowSpec:
    config_path = project_dir.resolve() / "opc.toml"
    if not config_path.exists():
        return DEFAULT_WORKFLOW_SPEC
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    spec_data = data.get("workflow_spec")
    if not isinstance(spec_data, dict):
        return DEFAULT_WORKFLOW_SPEC
    return WorkflowSpec.from_dict(spec_data)


# 默认阶段执行契约：完整 DAG 字段先作为可验证契约落地，运行时仍由 HarnessWorkflow 小步接入。
DEFAULT_STAGE_CONTRACTS = [
    StageContract(
        name="pm",
        role="pm",
        input_schema="ContextPack",
        output_schema="PMOutput",
        artifact="pm_prd",
        validation=["required_fields", "acceptance_criteria"],
        transition=TransitionPolicy(on_pass="已定义", on_fail="待澄清", on_error="待澄清"),
    ),
    StageContract(
        name="architect",
        role="architect",
        input_schema="ContextPack",
        output_schema="markdown_architecture",
        artifact="architecture",
        validation=["scope_alignment", "risk_review"],
        transition=TransitionPolicy(on_pass="已设计", on_fail="已定义", on_error="已定义"),
        parallel_group="growth_architect",
    ),
    StageContract(
        name="growth",
        role="growth",
        input_schema="ContextPack",
        output_schema="markdown_growth_research",
        artifact="growth_research",
        validation=["source_attribution"],
        transition=TransitionPolicy(on_pass="已调研", on_fail="已定义", on_error="已定义"),
        parallel_group="growth_architect",
    ),
    StageContract(
        name="engineer",
        role="engineer",
        input_schema="ContextPack",
        output_schema="EngineerOutput",
        artifact="implementation",
        validation=["changed_files", "test_result_or_failure_reason"],
        tools=["read_file", "grep", "search_knowledge", "write_file", "run_tests", "run_lint", "run_typecheck"],
        transition=TransitionPolicy(on_pass="实现中", on_fail="已退回", on_error="已退回", retry_limit=1),
        failure_branch="已退回",
        retry_policy={"max_attempts": 1, "on_exhausted": "human_intervention"},
    ),
    StageContract(
        name="qa",
        role="qa",
        input_schema="ContextPack",
        output_schema="QAOutput",
        artifact="qa_report",
        validation=["status", "evidence", "defects_on_fail", "rollback_stage"],
        tools=["read_file", "grep", "run_tests", "git_diff"],
        transition=TransitionPolicy(on_pass="已通过", on_fail="已退回", on_error="已退回", failure_branch="已退回"),
        conditional_branches={"done": "已通过", "rework": "已退回", "human_intervention": "已退回"},
        failure_branch="已退回",
    ),
    StageContract(
        name="ops",
        role="ops",
        input_schema="ContextPack",
        output_schema="markdown_ops_check",
        artifact="ops_check",
        validation=["runtime_check", "rollback_note"],
        tools=["run_tests", "run_build", "git_status"],
        transition=TransitionPolicy(on_pass="已运行检查", on_fail="已退回", on_error="已退回"),
    ),
    StageContract(
        name="retro",
        role="pm",
        input_schema="WorkflowState",
        output_schema="markdown_retrospective",
        artifact="retrospective",
        validation=["final_status", "lessons"],
        transition=TransitionPolicy(on_pass="已复盘", on_fail="已复盘"),
    ),
]


# 默认 MVP 工作流 spec
DEFAULT_WORKFLOW_SPEC = WorkflowSpec(
    name="mvp_pm_engineer_qa",
    states=["待澄清", "已调研", "已定义", "已设计", "实现中", "待验收", "已运行检查", "已通过", "已退回", "已复盘"],
    stages=[
        WorkflowStage("growth", "已调研", optional_role="growth", parallel_group="growth_architect"),
        WorkflowStage("pm", "已定义"),
        WorkflowStage("architect", "已设计", optional_role="architect", parallel_group="growth_architect"),
        WorkflowStage("engineer", "实现中"),
        WorkflowStage("qa", "待验收"),
        WorkflowStage("ops", "已运行检查", optional_role="ops"),
        WorkflowStage("retro", "已复盘", approval_required=False),
    ],
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
