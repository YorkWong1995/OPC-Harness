"""Harness 工作流状态机：驱动 PM → Engineer → QA 的最小闭环"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .roles import (
    create_pm_agent,
    create_engineer_agent,
    create_embedded_engineer_agent,
    create_qa_agent,
    create_architect_agent,
    create_ceo_agent,
    create_ops_agent,
    create_growth_agent,
    infer_optional_roles,
    RETROSPECTIVE_PROMPT,
)
from .config import load_workflow_config
from .config import load_project_config, OPCConfig
from .run_store import RunStore
from .knowledge.impact_analyzer import ImpactAnalyzer
from .schema import ContextPack, EngineerOutput, PMOutput, QAOutput, StageSummary, parse_role_output
from .security.guardrail import GuardrailPolicy, normalize_permission_profile
from .memory import MemoryRecord, MemoryStore, select_memory_for_context
from .store import Store
from .workflow_spec import StageResult, StageValidation, load_workflow_spec

console = Console()


class _GoBack(Exception):
    """退回到上一阶段的信号。"""
    pass


class _StopWorkflow(Exception):
    """终止工作流的信号。"""
    pass


@dataclass
class WorkflowState:
    """工作流状态持久化结构，用于保存和恢复工作流执行进度。"""

    current_stage: str = "待澄清"
    completed_stages: list[str] = field(default_factory=list)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    task_description: str = ""
    run_id: str = ""
    rework_attempts: int = 0
    # 每阶段的执行指标：键为阶段名（如 "已定义"），值包含 input_tokens / output_tokens / duration_seconds / tool_calls
    stage_logs: dict[str, dict] = field(default_factory=dict)
    stage_summaries: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load_state(cls, artifacts_dir: Path) -> "WorkflowState":
        """从 artifacts/.opc_state.json 恢复 WorkflowState。

        Args:
            artifacts_dir: artifacts 目录路径

        Returns:
            恢复的 WorkflowState 实例

        Raises:
            FileNotFoundError: 状态文件不存在
            json.JSONDecodeError: 状态文件内容不是合法 JSON
        """
        state_path = artifacts_dir / ".opc_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return cls(**data)


def generate_run_report(state: WorkflowState, artifacts_dir: Path) -> Path:
    """从 WorkflowState 生成 artifacts/run_report.md。

    报告包含：任务描述、各阶段耗时与 token 消耗、产物路径汇总。

    Args:
        state: 当前工作流状态
        artifacts_dir: artifacts 目录路径

    Returns:
        生成的 run_report.md 文件路径
    """
    lines: list[str] = []
    lines.append("# OPC Run Report")
    lines.append("")
    lines.append(f"- **生成时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"- **最终阶段**: {state.current_stage}")
    lines.append("")

    # 任务描述
    lines.append("## 任务描述")
    lines.append("")
    lines.append(state.task_description or "(无)")
    lines.append("")

    # 阶段执行日志
    lines.append("## 阶段执行日志")
    lines.append("")
    if state.stage_logs:
        lines.append("| 阶段 | 耗时(s) | Input Tokens | Output Tokens |")
        lines.append("|------|---------|--------------|---------------|")
        total_duration = 0.0
        total_input = 0
        total_output = 0
        for stage_name, log in state.stage_logs.items():
            duration = log.get("duration_seconds", 0)
            inp = log.get("input_tokens", 0)
            out = log.get("output_tokens", 0)
            total_duration += duration
            total_input += inp
            total_output += out
            lines.append(f"| {stage_name} | {duration} | {inp} | {out} |")
        lines.append(f"| **合计** | **{round(total_duration, 2)}** | **{total_input}** | **{total_output}** |")
    else:
        lines.append("(无阶段日志)")
    lines.append("")

    # 产物路径
    lines.append("## 产物路径")
    lines.append("")
    if state.artifact_paths:
        for name, path in state.artifact_paths.items():
            lines.append(f"- **{name}**: `{path}`")
    else:
        lines.append("(无产物)")
    lines.append("")

    # 已完成阶段
    lines.append("## 已完成阶段")
    lines.append("")
    if state.completed_stages:
        lines.append(" → ".join(state.completed_stages))
    else:
        lines.append("(无)")
    lines.append("")

    report_content = "\n".join(lines)
    report_path = artifacts_dir / "run_report.md"
    report_path.write_text(report_content, encoding="utf-8")
    return report_path


def generate_metrics(state: WorkflowState, artifacts_dir: Path) -> Path:
    """生成 artifacts/run_metrics.json。"""
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "duration_seconds": 0.0,
        "tool_calls": 0,
        "api_calls": 0,
    }
    for key, log in state.stage_logs.items():
        if key.startswith("_") or not isinstance(log, dict):
            continue
        totals["input_tokens"] += int(log.get("input_tokens", 0) or 0)
        totals["output_tokens"] += int(log.get("output_tokens", 0) or 0)
        totals["duration_seconds"] += float(log.get("duration_seconds", 0) or 0)
        totals["tool_calls"] += int(log.get("tool_calls", 0) or 0)
        totals["api_calls"] += int(log.get("api_calls", 0) or 0)
    totals["duration_seconds"] = round(totals["duration_seconds"], 2)

    # 质量指标
    qa_passed = state.current_stage in ("已通过", "已运行检查", "已复盘")
    quality = {
        "qa_passed": qa_passed,
        "rework_attempts": state.rework_attempts,
        "human_interventions": state.stage_logs.get("_human_interventions", 0),
        "failure_types": state.stage_logs.get("_failure_types", {}),
        "validation_runs": state.stage_logs.get("_validation_runs", 0),
        "self_repair_attempts": state.stage_logs.get("_self_repair_attempts", 0),
        "self_repair_successes": state.stage_logs.get("_self_repair_successes", 0),
    }

    metrics = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "task_description": state.task_description,
        "current_stage": state.current_stage,
        "stages": {k: v for k, v in state.stage_logs.items() if not k.startswith("_")},
        "totals": totals,
        "quality": quality,
        "artifacts": state.artifact_paths,
    }
    metrics_path = artifacts_dir / "run_metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics_path


def _metric_int(value) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


# 状态流转（参照 plan.md 9.4节）
STATES = [
    "待澄清",
    "已调研",
    "已定义",
    "已设计",
    "实现中",
    "待验收",
    "已通过",
    "已运行检查",
    "已退回",
    "已复盘",
]


ROLE_CONTEXT_SECTIONS = {
    "pm": {"task_goal", "acceptance", "constraints", "facts", "history_summary", "context_sources"},
    "growth": {"task_goal", "constraints", "facts", "risks", "history_summary", "context_sources"},
    "architect": {"task_goal", "acceptance", "constraints", "facts", "decisions", "stage_summary", "related_files", "risks", "history_summary", "context_sources"},
    "engineer": {"task_goal", "acceptance", "constraints", "facts", "decisions", "open_questions", "stage_summary", "related_files", "diff_summary", "validation", "risks", "history_summary", "context_sources"},
    "qa": {"task_goal", "acceptance", "constraints", "facts", "decisions", "stage_summary", "related_files", "diff_summary", "validation", "risks", "history_summary", "context_sources"},
    "ops": {"task_goal", "acceptance", "stage_summary", "related_files", "diff_summary", "validation", "risks", "history_summary", "context_sources"},
}


class HarnessWorkflow:
    """最小 harness 工作流

    状态流转：待澄清 → 已定义 → 实现中 → 待验收 → 已通过/已退回 → 已复盘
    """

    def __init__(
        self,
        task: str,
        project_dir: Path,
        auto_confirm: bool = False,
        ceo_review: bool = False,
        skip_architect: bool = False,
        roles: set[str] | None = None,
        model: str | None = None,
        use_embedded_engineer: bool = False,
        profile: str = "default",
    ):
        self.task = task
        self.project_dir = project_dir.resolve()
        self.store = Store(self.project_dir / "artifacts")
        self.state = "待澄清"
        self.auto_confirm = auto_confirm
        self.roles = set(roles) if roles is not None else infer_optional_roles(task)
        if ceo_review:
            self.roles.add("ceo")
        if skip_architect:
            self.roles.discard("architect")
        self.profile = profile
        # profile="embedded" 自动启用 embedded_engineer 并跳过 architect
        if profile == "embedded":
            use_embedded_engineer = True
            self.roles.discard("architect")
        self.model = model
        self.use_embedded_engineer = use_embedded_engineer

        self.workflow_config = load_workflow_config(self.project_dir, profile)
        self.opc_config = load_project_config(self.project_dir, profile)
        self.max_rework_attempts = self.workflow_config.max_rework_attempts
        self.max_rounds = self.workflow_config.max_rounds
        self.run_store = RunStore(self.store.dir)
        self.workflow_state = WorkflowState(task_description=task, run_id=self.run_store.run_id)
        self.workflow_spec = load_workflow_spec(self.project_dir)
        self.stage_summaries: dict[str, StageSummary] = {}
        self.memory_store = MemoryStore(self.project_dir / "artifacts" / "memory.jsonl")
        self.memory_records: list[MemoryRecord] = self.memory_store.load()
        self.last_edited_prompt: str = ""

        self.pm = create_pm_agent(model=model)

        # 根据配置选择 Engineer 类型
        if use_embedded_engineer:
            self.engineer = create_embedded_engineer_agent(self.project_dir, model=model)
        else:
            self.engineer = create_engineer_agent(self.project_dir, model=model)

        self.qa = create_qa_agent(self.project_dir, model=model)
        self.ceo = create_ceo_agent(model=model) if self.enabled("ceo") else None
        self.architect = create_architect_agent(self.project_dir, model=model) if self.enabled("architect") else None
        self.ops = create_ops_agent(self.project_dir, model=model) if self.enabled("ops") else None
        self.growth = create_growth_agent(model=model) if self.enabled("growth") else None
        self._configure_agent_guardrails()

    def _configure_agent_guardrails(self) -> None:
        security = self.opc_config.security
        for agent in [self.pm, self.engineer, self.qa, self.ceo, self.architect, self.ops, self.growth]:
            if agent is None:
                continue
            agent.run_store = self.run_store
            agent.guardrail_policy = GuardrailPolicy(
                profile=normalize_permission_profile(security.permission_profile),
                dangerous_command_policy=security.dangerous_command_policy,
            )

    def enabled(self, role: str) -> bool:
        """判断可选角色是否启用。"""
        return role in self.roles

    async def _run_stage(self, agent, prompt: str, stage_name: str) -> str:
        """运行 agent 并记录耗时和 token 到 stage_logs。"""
        self.run_store.append("stage_started", stage=stage_name, role=getattr(agent, "role", stage_name), prompt=prompt)
        start = time.monotonic()
        result = await asyncio.to_thread(agent.run, prompt)
        duration = time.monotonic() - start
        self._record_stage_metrics(agent, stage_name, duration)

        # 记录工具调用和结果
        if hasattr(agent, "audit_log") and agent.audit_log:
            for tool_record in agent.audit_log:
                self.run_store.append(
                    "tool_call",
                    stage=stage_name,
                    role=getattr(agent, "role", stage_name),
                    **tool_record
                )
                self._write_tool_audit(stage_name, getattr(agent, "role", stage_name), tool_record)
            # 清空审计日志，避免重复记录
            agent.audit_log.clear()

        self.run_store.append(
            "stage_completed",
            stage=stage_name,
            role=getattr(agent, "role", stage_name),
            duration_seconds=round(duration, 2),
            input_tokens=getattr(agent, "last_input_tokens", 0),
            output_tokens=getattr(agent, "last_output_tokens", 0),
            tool_calls=getattr(agent, "last_tool_calls", 0),
            api_calls=getattr(agent, "last_api_calls", 0),
            output=result,
        )
        return result

    def _record_stage_metrics(self, agent, stage_name: str, duration: float):
        input_tokens = _metric_int(getattr(agent, "last_input_tokens", 0))
        output_tokens = _metric_int(getattr(agent, "last_output_tokens", 0))
        tool_calls = _metric_int(getattr(agent, "last_tool_calls", 0))
        api_calls = _metric_int(getattr(agent, "last_api_calls", 0))
        self.workflow_state.stage_logs[stage_name] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_seconds": round(duration, 2),
            "tool_calls": tool_calls,
            "api_calls": api_calls,
        }
        self._observe_cost_limits(stage_name, input_tokens + output_tokens, api_calls)

    def _write_tool_audit(self, stage: str, role: str, record: dict):
        """将工具调用写入独立审计日志文件"""
        audit_path = self.store.dir / "tool_audit.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_store.run_id,
            "stage": stage,
            "role": role,
            "tool_name": record.get("tool_name"),
            "inputs": record.get("inputs"),
            "elapsed": record.get("elapsed"),
            "error": record.get("error"),
        }
        with audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _open_circuit_breaker(self, reason: str, **payload) -> None:
        self.run_store.append(
            "circuit_breaker_open",
            reason=reason,
            default_action="stop_workflow",
            **payload,
        )

    def _record_rollback_decision(
        self,
        from_stage: str,
        to_stage: str,
        reason: str,
        default_action: str = "rerun_target_stage",
        **payload,
    ) -> None:
        self.run_store.append(
            "rollback_decision",
            from_stage=from_stage,
            to_stage=to_stage,
            reason=reason,
            default_action=default_action,
            **payload,
        )

    def _observe_cost_limits(self, stage_name: str, stage_tokens: int, stage_api_calls: int):
        """观测成本限制：soft_limit 仅警告，hard_limit 触发 _StopWorkflow"""
        cost = self.opc_config.cost

        # 计算工作流总 token
        total_tokens = sum(
            int(log.get("input_tokens", 0) or 0) + int(log.get("output_tokens", 0) or 0)
            for key, log in self.workflow_state.stage_logs.items()
            if isinstance(log, dict) and not key.startswith("_")
        )

        if total_tokens > cost.workflow_token_limit:
            print(f"[WARN] 工作流 token 用量 ({total_tokens}) 超过配置上限 ({cost.workflow_token_limit})")
            self.run_store.append("cost_warning", kind="workflow_token_limit",
                                 current=total_tokens, limit=cost.workflow_token_limit)

        if stage_tokens > cost.role_token_limit:
            print(f"[WARN] 角色 {stage_name} token 用量 ({stage_tokens}) 超过配置上限 ({cost.role_token_limit})")
            self.run_store.append("cost_warning", kind="role_token_limit",
                                 stage=stage_name, current=stage_tokens, limit=cost.role_token_limit)

        # 硬限制：超过即中止
        if cost.enforce_hard_limit:
            if cost.workflow_token_hard_limit and total_tokens > cost.workflow_token_hard_limit:
                msg = (f"工作流 token 用量 ({total_tokens}) 超过硬上限 "
                       f"({cost.workflow_token_hard_limit})，中止工作流")
                print(f"[ERROR] {msg}")
                self._open_circuit_breaker(
                    "workflow_token_hard_limit",
                    kind="workflow_token_hard_limit",
                    current=total_tokens,
                    limit=cost.workflow_token_hard_limit,
                )
                self.run_store.append("cost_hard_limit", kind="workflow_token_hard_limit",
                                     current=total_tokens, limit=cost.workflow_token_hard_limit)
                raise _StopWorkflow(msg)
            if cost.role_token_hard_limit and stage_tokens > cost.role_token_hard_limit:
                msg = (f"角色 {stage_name} token 用量 ({stage_tokens}) 超过硬上限 "
                       f"({cost.role_token_hard_limit})，中止工作流")
                print(f"[ERROR] {msg}")
                self._open_circuit_breaker(
                    "role_token_hard_limit",
                    kind="role_token_hard_limit",
                    stage=stage_name,
                    current=stage_tokens,
                    limit=cost.role_token_hard_limit,
                )
                self.run_store.append("cost_hard_limit", kind="role_token_hard_limit",
                                     stage=stage_name, current=stage_tokens,
                                     limit=cost.role_token_hard_limit)
                raise _StopWorkflow(msg)

    async def _run_stages_parallel(self, stage_specs: list[tuple[object, str, str]]) -> list[str]:
        return await asyncio.gather(*(self._run_stage(*spec) for spec in stage_specs))

    def save_state(self):
        """将当前 WorkflowState 序列化为 JSON 写入 artifacts/.opc_state.json"""
        self.workflow_state.current_stage = self.state
        if not self.workflow_state.run_id:
            self.workflow_state.run_id = self.run_store.run_id
        state_path = self.store.dir / ".opc_state.json"
        state_path.write_text(
            json.dumps(asdict(self.workflow_state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _create_stage_summary(
        self,
        stage: str,
        goal: str = "",
        decisions: list[str] | None = None,
        changed_files: list[str] | None = None,
        validation: list[str] | None = None,
        risks: list[str] | None = None,
        next_step: str = "",
    ) -> StageSummary:
        return StageSummary(
            stage=stage,
            goal=goal,
            decisions=decisions or [],
            changed_files=changed_files or [],
            validation=validation or [],
            risks=risks or [],
            next_step=next_step,
        )

    def _record_stage_summary(self, key: str, summary: StageSummary) -> None:
        self.stage_summaries[key] = summary
        self.workflow_state.stage_summaries[key] = summary.model_dump()
        self.run_store.append(
            "stage_summary_created",
            key=key,
            stage=summary.stage,
            summary=summary.model_dump(),
        )

    def _build_sliding_context(self, purpose: str, recent_detail: str = "") -> str:
        pm_summary = self.stage_summaries.get("pm")
        goal = pm_summary.goal if pm_summary else self.task
        acceptance = pm_summary.validation if pm_summary else []
        summaries = [
            f"- {key}: {summary.model_dump_json()}"
            for key, summary in self.stage_summaries.items()
        ]
        sections = [
            f"用途：{purpose}",
            f"任务目标：{goal}",
            "验收标准：\n" + ("\n".join(f"- {item}" for item in acceptance) if acceptance else "- 未提供"),
            "历史阶段摘要：\n" + ("\n".join(summaries) if summaries else "- 暂无"),
        ]
        if recent_detail:
            sections.append(f"最近一轮详细内容：\n{recent_detail}")
        return "\n\n".join(sections)

    @staticmethod
    def _tailor_context_pack(pack: ContextPack, role: str) -> tuple[ContextPack, list[str]]:
        allowed = ROLE_CONTEXT_SECTIONS.get(role, ROLE_CONTEXT_SECTIONS["engineer"])
        data = pack.model_dump()
        for field, value in list(data.items()):
            if field in allowed:
                continue
            if isinstance(value, list):
                data[field] = []
            elif isinstance(value, dict):
                data[field] = {}
            else:
                data[field] = ""
        return ContextPack.model_validate(data), sorted(allowed)

    def _select_memory_context(self, role: str, facts: list[str]) -> tuple[list[str], list[dict[str, str]]]:
        records, sources = select_memory_for_context(
            self.memory_records,
            role=role,
            current_facts=set(facts),
        )
        return [f"memory.{record.scope}: {record.content}" for record in records], sources

    def _build_context_pack(self, role: str, stage: str, recent_detail: str = "") -> ContextPack:
        pm_summary = self.stage_summaries.get("pm")
        stage_summary = {key: summary.model_dump() for key, summary in self.stage_summaries.items()}
        related_files: list[str] = []
        validation: list[str] = []
        risks: list[str] = []
        facts: list[str] = []
        decisions: list[str] = []
        open_questions: list[str] = []
        context_sources: list[dict[str, str]] = []
        for key, summary in self.stage_summaries.items():
            if summary.goal:
                facts.append(f"{summary.stage}.goal: {summary.goal}")
            decisions.extend(summary.decisions)
            related_files.extend(summary.changed_files)
            validation.extend(summary.validation)
            risks.extend(summary.risks)
            if summary.next_step and summary.next_step not in {"engineer", "qa", "done", "pass"}:
                open_questions.append(f"{summary.stage}.next_step: {summary.next_step}")
            context_sources.append({"type": "stage_summary", "name": key})
        impact_summary = "impact_analysis=not_run"
        if related_files:
            try:
                impact = ImpactAnalyzer(self.project_dir).analyze(sorted(set(related_files)))
                related_files.extend(impact.related_files)
                related_files.extend(impact.related_tests)
                validation.extend(impact.validation_commands)
                risks.extend(impact.risk_points)
                context_sources.append({"type": "analysis", "name": "impact_analyzer"})
                impact_summary = (
                    f"impact_analysis=related_files:{len(impact.related_files)},"
                    f"tests:{len(impact.related_tests)},risks:{len(impact.risk_points)}"
                )
            except Exception as error:
                impact_summary = f"impact_analysis=failed:{error}"
        if recent_detail:
            context_sources.append({"type": "recent_detail", "name": f"{role}:{stage}"})
        memory_facts, memory_sources = self._select_memory_context(role, facts)
        facts.extend(memory_facts)
        context_sources.extend(memory_sources)
        context_sources.extend(
            {"type": "artifact", "name": name, "path": path}
            for name, path in self.workflow_state.artifact_paths.items()
        )
        pack = ContextPack(
            task_goal=pm_summary.goal if pm_summary else self.task,
            acceptance=pm_summary.validation if pm_summary else [],
            constraints=pm_summary.risks if pm_summary else [],
            facts=facts,
            decisions=decisions,
            open_questions=open_questions,
            stage_summary=stage_summary,
            related_files=sorted(set(related_files)),
            diff_summary=recent_detail,
            validation=validation,
            risks=risks,
            history_summary=f"role={role}; stage={stage}; summaries={', '.join(stage_summary) or 'none'}; {impact_summary}",
            context_sources=context_sources,
        )
        pack, included_sections = self._tailor_context_pack(pack, role)
        if hasattr(self, "run_store"):
            self.run_store.append(
                "context_pack_created",
                role=role,
                stage=stage,
                included_sections=included_sections,
                source_artifacts=list(getattr(self.workflow_state, "artifact_paths", {}).keys()),
                summary_used=list(stage_summary.keys()),
                context_sources=context_sources,
                impact_summary=impact_summary,
                excluded_reason="historical full text replaced by stage_summary; only recent_detail is carried",
            )
        return pack

    async def run(self, resume_from: str | None = None):
        """运行工作流。

        Args:
            resume_from: 从指定阶段继续执行，跳过该阶段之前的已完成阶段。
                         有效值为 STATES 中的状态名，如 "已定义"、"实现中" 等。
                         为 None 时从头开始执行。
        """
        if resume_from:
            if resume_from not in STATES:
                raise ValueError(f"无效的阶段名: {resume_from}，有效值: {STATES}")
            # 从持久化状态恢复
            self.workflow_state = WorkflowState.load_state(self.store.dir)
            self.state = self.workflow_state.current_stage
            self.run_store = RunStore.load(self.store.dir)
            if self.workflow_state.run_id:
                self.run_store.run_id = self.workflow_state.run_id
            self.stage_summaries = {
                key: StageSummary.model_validate(summary)
                for key, summary in self.workflow_state.stage_summaries.items()
            }
            console.print(Panel(
                f"[bold]任务[/]: {self.task}\n[yellow]从阶段 [{resume_from}] 恢复执行[/yellow]",
                title="OPC Harness 工作流恢复",
            ))
        else:
            console.print(Panel(f"[bold]任务[/]: {self.task}", title="OPC Harness 工作流启动"))

        def should_skip(stage: str) -> bool:
            """判断是否跳过该阶段（resume_from 模式下，已完成的阶段跳过）"""
            if not resume_from:
                return False
            return stage in self.workflow_state.completed_stages

        def load_artifact(name: str) -> str | None:
            """从 artifacts 目录加载已有产物内容"""
            artifact_path = self.workflow_state.artifact_paths.get(name)
            if artifact_path:
                p = Path(artifact_path)
                if p.exists():
                    return p.read_text(encoding="utf-8")
            return None

        # 阶段间共享的产物
        outputs: dict[str, str] = {"growth": "", "prd": "", "architecture": "", "implementation": "", "acceptance": "", "ops": ""}

        active_stages = self.workflow_spec.runtime_stages(self.roles)

        stage_idx = 0
        rounds = 0
        while stage_idx < len(active_stages):
            rounds += 1
            if rounds > self.max_rounds:
                self.state = "已退回"
                self._open_circuit_breaker(
                    "max_rounds_exceeded",
                    stage="workflow",
                    current_round=rounds,
                    limit=self.max_rounds,
                )
                self.run_store.append("workflow_stopped", reason="max_rounds_exceeded", max_rounds=self.max_rounds)
                self.save_state()
                return
            current = active_stages[stage_idx]
            try:
                await self._run_stage_by_name(current, outputs, should_skip, load_artifact)
                stage_idx = self._next_stage_index(active_stages, stage_idx, condition="pass")
            except _GoBack:
                if stage_idx > 0:
                    # 从 completed_stages 中移除当前阶段和目标阶段，以便重新执行
                    prev = active_stages[stage_idx - 1]
                    prev_state_name = self._stage_to_state_name(prev)
                    cur_state_name = self._stage_to_state_name(current)
                    if cur_state_name in self.workflow_state.completed_stages:
                        self.workflow_state.completed_stages.remove(cur_state_name)
                    if prev_state_name in self.workflow_state.completed_stages:
                        self.workflow_state.completed_stages.remove(prev_state_name)
                    self._record_rollback_decision(
                        from_stage=current,
                        to_stage=prev,
                        reason="manual_go_back",
                        default_action="rerun_previous_stage",
                    )
                    self.save_state()
                    stage_idx -= 1
                    console.print(f"[yellow]退回到上一阶段: {prev}[/yellow]")
                else:
                    # 第一个阶段无法退回，清除已完成标记后重做当前阶段
                    cur_state_name = self._stage_to_state_name(current)
                    if cur_state_name in self.workflow_state.completed_stages:
                        self.workflow_state.completed_stages.remove(cur_state_name)
                    self._record_rollback_decision(
                        from_stage=current,
                        to_stage=current,
                        reason="manual_go_back_at_first_stage",
                        default_action="rerun_current_stage",
                    )
                    self.save_state()
                    console.print("[yellow]已经是第一个阶段，将重做当前阶段。[/yellow]")
            except _StopWorkflow:
                return

        console.print("\n[bold green]工作流完成！[/] 所有产物已保存到 artifacts/ 目录。")
        metrics_path = generate_metrics(self.workflow_state, self.store.dir)
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.memory_store.replace(self.memory_records)
        self.run_store.write_trace(final_status=self.state, metrics=metrics)

    @staticmethod
    def _stage_to_state_name(stage: str) -> str:
        """将内部阶段标识映射为 WorkflowState 中的状态名。"""
        mapping = {
            "growth": "已调研",
            "pm": "已定义",
            "growth_architect": "已设计",
            "architect": "已设计",
            "engineer": "实现中",
            "qa": "待验收",
            "ops": "已运行检查",
            "retro": "已复盘",
        }
        return mapping.get(stage, stage)

    @staticmethod
    def _state_to_stage_name(state: str) -> str | None:
        mapping = {
            "已调研": "growth",
            "已定义": "pm",
            "已设计": "architect",
            "实现中": "engineer",
            "待验收": "qa",
            "已复盘": "retro",
        }
        return mapping.get(state)

    def _next_stage_index(self, active_stages: list[str], stage_idx: int, condition: str = "pass") -> int:
        """用 WorkflowSpec 计算下一阶段，同时不跳过 active_stages 中插入的可选阶段。"""
        current_stage = active_stages[stage_idx]
        current_state = self._stage_to_state_name(current_stage)
        next_state = self.workflow_spec.next_state(current_state, condition)
        if next_state is None:
            return stage_idx + 1

        visited: set[str] = set()
        while next_state and next_state not in visited:
            visited.add(next_state)
            next_stage = self._state_to_stage_name(next_state)
            if next_stage in active_stages:
                next_idx = active_stages.index(next_stage)
                # 不允许声明式主链路跳过运行时插入的 Architect/Ops/Growth 等阶段。
                if next_idx <= stage_idx + 1:
                    return next_idx
                return stage_idx + 1
            if self.workflow_spec.is_terminal(next_state):
                return len(active_stages)
            next_state = self.workflow_spec.next_state(next_state, "pass")

        return stage_idx + 1

    async def _run_stage_by_name(self, stage: str, outputs: dict, should_skip, load_artifact):
        """根据阶段名执行对应逻辑。完成后更新 outputs 字典。"""
        handler_map = {
            "growth": self._exec_growth,
            "pm": self._exec_pm,
            "growth_architect": self._exec_growth_architect_parallel,
            "architect": self._exec_architect,
            "engineer": self._exec_engineer,
            "qa": self._exec_qa,
            "ops": self._exec_ops,
            "retro": self._exec_retro,
        }
        handler = handler_map.get(stage)
        if handler is None:
            raise ValueError(f"未知工作流阶段: {stage}")
        await handler(outputs, should_skip, load_artifact)

    async def _exec_growth_architect_parallel(self, outputs, should_skip, load_artifact):
        """并行执行 Growth 与 Architect 阶段。"""
        skip_growth = should_skip("已调研")
        skip_architect = should_skip("已设计")
        if skip_growth:
            outputs["growth"] = load_artifact("growth") or ""
        if skip_architect:
            outputs["architecture"] = load_artifact("architecture") or ""
        if skip_growth and skip_architect:
            console.print("[dim]跳过 Growth/Architect 并行阶段（已完成）[/dim]")
            return

        growth_prompt = f"基于以下任务产出 Growth / Research 建议：\n\n{self.task}"
        arch_prompt = f"基于以下 PRD 产出架构方案：\n\n{outputs['prd']}"
        specs = []
        if not skip_growth:
            specs.append((self.growth, growth_prompt, "已调研"))
        if not skip_architect:
            specs.append((self.architect, arch_prompt, "已设计"))

        console.print("\n[bold cyan][Growth/Architect][/bold cyan] 正在并行产出研究建议与架构方案...")
        results = await self._run_stages_parallel(specs)
        result_idx = 0
        if not skip_growth:
            growth = results[result_idx]
            result_idx += 1
            growth_path = self.store.save("growth.md", growth)
            outputs["growth"] = growth
            if "已调研" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已调研")
            self.workflow_state.artifact_paths["growth"] = str(growth_path)
            console.print(f"[green]研究建议已保存[/]: {growth_path}")
        if not skip_architect:
            architecture = results[result_idx]
            arch_path = self.store.save("architecture.md", architecture)
            outputs["architecture"] = architecture
            if "已设计" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已设计")
            self.workflow_state.artifact_paths["architecture"] = str(arch_path)
            console.print(f"[green]架构说明已保存[/]: {arch_path}")
        self.state = "已设计"
        self.save_state()
        decision = self.review("Growth 与 Architect 已并行产出，是否继续让 Engineer 实现？", outputs["architecture"], arch_prompt)
        if decision == "n":
            raise _StopWorkflow()
        if decision == "r":
            raise _GoBack()

    async def _exec_growth(self, outputs, should_skip, load_artifact):
        """Growth / Research 阶段。"""
        if should_skip("已调研"):
            outputs["growth"] = load_artifact("growth") or ""
            console.print("[dim]跳过 Growth 阶段（已完成）[/dim]")
            return
        growth_prompt = f"基于以下任务产出 Growth / Research 建议：\n\n{self.task}"
        while True:
            console.print("\n[bold cyan][Growth][/bold cyan] 正在产出研究建议...")
            growth = await self._run_stage(self.growth, growth_prompt, "已调研")
            growth_path = self.store.save("growth.md", growth)
            self.state = "已调研"
            if "已调研" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已调研")
            self.workflow_state.artifact_paths["growth"] = str(growth_path)
            self.save_state()
            console.print(f"[green]研究建议已保存[/]: {growth_path}")
            console.print(Panel(growth[:800] + ("..." if len(growth) > 800 else ""), title="研究建议预览"))
            decision = self.review("Growth 已产出研究建议，是否继续让 PM 产出 PRD？", growth, growth_prompt)
            if decision == "y":
                outputs["growth"] = growth
                return
            elif decision == "n":
                raise _StopWorkflow()
            elif decision == "e":
                growth_prompt = self.last_edited_prompt
            elif decision == "r":
                raise _GoBack()

    async def _exec_pm(self, outputs, should_skip, load_artifact):
        """PM 产出 PRD 阶段。"""
        if should_skip("已定义"):
            outputs["prd"] = load_artifact("prd") or ""
            console.print("[dim]跳过 PM/PRD 阶段（已完成）[/dim]")
            return
        if outputs["growth"]:
            pm_input = f"基于以下任务和 Growth 建议产出 PRD：\n\n任务：\n{self.task}\n\nGrowth 建议：\n{outputs['growth']}"
        else:
            pm_input = self.task
        prd_prompt = pm_input
        while True:
            console.print("\n[bold cyan][PM][/bold cyan] 正在产出 PRD...")
            prd = await self._run_stage(self.pm, prd_prompt, "已定义")
            prd_path = self.store.save("prd.md", prd)
            pm_output = self._parse_role_output("pm", prd)
            self.state = "已定义"
            if "已定义" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已定义")
            self.workflow_state.artifact_paths["prd"] = str(prd_path)
            if isinstance(pm_output, PMOutput):
                self._record_stage_summary(
                    "pm",
                    self._create_stage_summary(
                        stage="pm",
                        goal=pm_output.goal,
                        decisions=pm_output.scope,
                        validation=pm_output.acceptance_criteria,
                        risks=pm_output.risks,
                        next_step="engineer",
                    ),
                )
            self.save_state()
            console.print(f"[green]PRD 已保存[/]: {prd_path}")
            console.print(Panel(prd[:800] + ("..." if len(prd) > 800 else ""), title="PRD 预览"))
            decision = self.review("PM 已产出 PRD，是否继续？", prd, prd_prompt)
            if decision == "y":
                outputs["prd"] = prd
                return
            elif decision == "n":
                raise _StopWorkflow()
            elif decision == "e":
                prd_prompt = self.last_edited_prompt
            elif decision == "r":
                raise _GoBack()

    async def _exec_architect(self, outputs, should_skip, load_artifact):
        """Architect 产出架构方案阶段。"""
        if should_skip("已设计"):
            outputs["architecture"] = load_artifact("architecture") or ""
            console.print("[dim]跳过 Architect 阶段（已完成）[/dim]")
            return
        arch_prompt = f"基于以下 PRD 产出架构方案：\n\n{outputs['prd']}"
        while True:
            console.print("\n[bold cyan][Architect][/bold cyan] 正在基于 PRD 产出架构方案...")
            architecture = await self._run_stage(self.architect, arch_prompt, "已设计")
            arch_path = self.store.save("architecture.md", architecture)
            self.state = "已设计"
            if "已设计" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已设计")
            self.workflow_state.artifact_paths["architecture"] = str(arch_path)
            self.save_state()
            console.print(f"[green]架构说明已保存[/]: {arch_path}")
            console.print(
                Panel(architecture[:800] + ("..." if len(architecture) > 800 else ""), title="架构说明预览")
            )
            decision = self.review("Architect 已产出架构方案，是否继续让 Engineer 实现？", architecture, arch_prompt)
            if decision == "y":
                outputs["architecture"] = architecture
                return
            elif decision == "n":
                raise _StopWorkflow()
            elif decision == "e":
                arch_prompt = self.last_edited_prompt
            elif decision == "r":
                raise _GoBack()

    async def _exec_engineer(self, outputs, should_skip, load_artifact):
        """Engineer 实现阶段。"""
        if should_skip("实现中"):
            outputs["implementation"] = load_artifact("implementation") or ""
            console.print("[dim]跳过 Engineer 阶段（已完成）[/dim]")
            return
        if outputs["architecture"]:
            context_pack = self._build_context_pack("engineer", "实现中", f"必要架构摘要：\n{outputs['architecture']}")
        else:
            context_pack = self._build_context_pack("engineer", "实现中")
        engineer_input = (
            "使用以下 Context Pack 完成实现。重点关注 task_goal、acceptance、constraints、"
            "stage_summary、validation 和 risks；如需原文细节，请读取已保存产物。\n\n"
            f"{context_pack.model_dump_json(indent=2)}"
        )
        eng_prompt = engineer_input
        while True:
            console.print("\n[bold cyan][Engineer][/bold cyan] 正在实现...")
            implementation = await self._run_stage(self.engineer, eng_prompt, "实现中")
            impl_path = self.store.save("implementation.md", implementation)
            engineer_output = self._parse_role_output("engineer", implementation)
            self.state = "实现中"
            if isinstance(engineer_output, EngineerOutput):
                engineer_risks = list(engineer_output.known_limits)
                if engineer_output.failure_reason:
                    engineer_risks.append(f"failure_reason: {engineer_output.failure_reason}")
                engineer_risks.extend(f"blocked_by: {item}" for item in engineer_output.blocked_by)
                self._record_stage_summary(
                    "engineer",
                    self._create_stage_summary(
                        stage="engineer",
                        goal="实现 PM 阶段定义的需求",
                        decisions=[engineer_output.implementation_summary],
                        changed_files=engineer_output.changed_files,
                        validation=[engineer_output.test_result] if engineer_output.test_result else [],
                        risks=engineer_risks,
                        next_step=engineer_output.suggested_next_step or "qa",
                    ),
                )
            if isinstance(engineer_output, EngineerOutput) and engineer_output.failure_reason:
                self.state = "已退回"
                self.run_store.append(
                    "engineer_failed",
                    failure_reason=engineer_output.failure_reason,
                    blocked_by=engineer_output.blocked_by,
                    suggested_next_step=engineer_output.suggested_next_step,
                )
                self.workflow_state.artifact_paths["implementation"] = str(impl_path)
                self.save_state()
                console.print("\n[bold red]Engineer 报告实现失败[/]，工作流暂停。")
                raise _StopWorkflow()
            if "实现中" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("实现中")
            self.workflow_state.artifact_paths["implementation"] = str(impl_path)
            self.save_state()
            console.print(f"[green]实现说明已保存[/]: {impl_path}")
            console.print(Panel(implementation[:800] + ("..." if len(implementation) > 800 else ""), title="实现说明预览"))
            decision = self.review("Engineer 已完成实现，是否继续让 QA 验收？", implementation, eng_prompt)
            if decision == "y":
                outputs["implementation"] = implementation
                return
            elif decision == "n":
                raise _StopWorkflow()
            elif decision == "e":
                eng_prompt = self.last_edited_prompt
            elif decision == "r":
                raise _GoBack()

    async def _exec_qa(self, outputs, should_skip, load_artifact):
        """QA 验收阶段：循环执行验收 → rework，直到通过或超出 rework 上限。

        旧实现以递归方式调用 self._exec_qa(...)，依赖 completed_stages 这种隐式
        不变量来保证不会重复进入；改为显式循环 + 显式状态变量更易理解和验证。
        """
        if should_skip("待验收") and should_skip("已通过"):
            outputs["acceptance"] = load_artifact("acceptance") or ""
            console.print("[dim]跳过 QA 阶段（已完成）[/dim]")
            return

        while True:
            console.print("\n[bold cyan][QA][/bold cyan] 正在基于验收标准检查实现...")
            context_pack = self._build_context_pack(
                "qa", "待验收", f"最近实现说明：\n{outputs['implementation']}"
            )
            if context_pack.validation:
                self.workflow_state.stage_logs["_validation_runs"] = (
                    self.workflow_state.stage_logs.get("_validation_runs", 0) + 1
                )
                self.run_store.append("validation_evidence", role="qa", commands=context_pack.validation)
            acceptance = await self._run_stage(
                self.qa,
                "使用以下 Context Pack 验收实现，重点关注 acceptance、stage_summary、"
                "related_files、validation 和 risks，必须给出 pass/fail：\n\n"
                f"{context_pack.model_dump_json(indent=2)}",
                "待验收",
            )
            acc_path = self.store.save("acceptance.md", acceptance)
            self.state = "待验收"
            if "待验收" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("待验收")
            self.workflow_state.artifact_paths["acceptance"] = str(acc_path)
            self.save_state()
            console.print(f"[green]验收记录已保存[/]: {acc_path}")
            console.print(
                Panel(acceptance[:800] + ("..." if len(acceptance) > 800 else ""), title="验收记录预览")
            )

            # 判断验收结果
            qa_output = self._parse_role_output("qa", acceptance)
            if isinstance(qa_output, QAOutput):
                qa_summary = self._create_stage_summary(
                    stage="qa",
                    goal="验证实现满足验收标准",
                    decisions=[
                        f"status: {qa_output.status}",
                        f"next_action: {qa_output.next_action}",
                        f"failure_root_cause: {qa_output.failure_root_cause}",
                        f"rollback_stage: {qa_output.rollback_stage}",
                    ],
                    validation=qa_output.checked_items + qa_output.evidence,
                    risks=qa_output.defects,
                    next_step=qa_output.next_action,
                )
                self._record_stage_summary("qa", qa_summary)
                if qa_output.status == "fail":
                    self._record_stage_summary(
                        f"qa_fail_{self.workflow_state.rework_attempts + 1}", qa_summary
                    )

            qa_failed = (
                qa_output.status == "fail"
                if isinstance(qa_output, QAOutput)
                else "不通过" in acceptance
            )
            if not qa_failed:
                self.state = "已通过"
                if "已通过" not in self.workflow_state.completed_stages:
                    self.workflow_state.completed_stages.append("已通过")
                self.save_state()
                console.print("\n[bold green]QA 验收通过[/]")
                outputs["acceptance"] = acceptance
                return

            # QA 不通过 → 触发 rework
            self.workflow_state.rework_attempts += 1
            self.state = "已退回"
            if "已退回" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已退回")
            self._record_rollback_decision(
                from_stage="qa",
                to_stage=qa_output.rollback_stage if isinstance(qa_output, QAOutput) and qa_output.rollback_stage else "engineer",
                reason="qa_failed",
                default_action="rework",
                rework_attempts=self.workflow_state.rework_attempts,
                defects=qa_output.defects if isinstance(qa_output, QAOutput) else [acceptance],
                failure_root_cause=qa_output.failure_root_cause if isinstance(qa_output, QAOutput) else "",
            )
            self.run_store.append(
                "qa_failed",
                rework_attempts=self.workflow_state.rework_attempts,
                defects=qa_output.defects if isinstance(qa_output, QAOutput) else [acceptance],
                failure_root_cause=qa_output.failure_root_cause if isinstance(qa_output, QAOutput) else "",
                rollback_stage=qa_output.rollback_stage if isinstance(qa_output, QAOutput) else "",
                diagnostic_summary=qa_output.diagnostic_summary if isinstance(qa_output, QAOutput) else "",
            )
            self.save_state()
            if self.workflow_state.rework_attempts > self.max_rework_attempts:
                console.print("\n[bold red]QA 验收未通过且超过最大返工次数[/]，工作流暂停。")
                self._open_circuit_breaker(
                    "max_rework_attempts_exceeded",
                    stage="qa",
                    rework_attempts=self.workflow_state.rework_attempts,
                    limit=self.max_rework_attempts,
                )
                raise _StopWorkflow()
            outputs["implementation"] = await self._run_rework(outputs, acceptance)
            # 继续下一轮 QA

    async def _run_rework(self, outputs: dict, acceptance: str) -> str:
        context_pack = self._build_context_pack(
            "engineer",
            "rework",
            f"QA defects：\n{acceptance}\n\n最近实现摘要：\n{outputs['implementation']}",
        )
        rework_prompt = (
            "使用以下 Context Pack 进行返工。重点关注 QA defects、最近实现摘要、"
            "task_goal、constraints、history_summary 和 risks，并输出新的结构化实现说明：\n\n"
            f"{context_pack.model_dump_json(indent=2)}"
        )
        console.print("\n[bold cyan][Engineer][/bold cyan] 正在根据 QA 缺陷返工...")
        implementation = await self._run_stage(self.engineer, rework_prompt, "实现中")
        impl_path = self.store.save("implementation.md", implementation)
        self._parse_role_output("engineer", implementation)
        self.workflow_state.artifact_paths["implementation"] = str(impl_path)
        self.state = "实现中"
        self.save_state()
        return implementation

    def _parse_role_output(self, role: str, content: str):
        contract = self.workflow_spec.stage_contracts().get(role)
        try:
            parsed = parse_role_output(role, content)
            artifact_paths = {
                name: path
                for name, path in self.workflow_state.artifact_paths.items()
                if not contract or name == contract.artifact or name == role
            }
            validation = StageValidation("passed")
            result = StageResult(
                stage=role,
                status="passed",
                output=parsed.model_dump(),
                artifact_paths=artifact_paths,
                validation=validation,
                next_state=contract.transition.on_pass if contract else "",
            )
            self.run_store.append(
                "role_output_validated",
                role=role,
                stage=role,
                output_schema=contract.output_schema if contract else type(parsed).__name__,
                artifact=contract.artifact if contract else "",
                validation=validation.status,
                next_state=result.next_state,
            )
            return parsed
        except Exception as error:
            validation = StageValidation(
                "failed",
                reason="role output does not match stage contract",
                schema_errors=[str(error)],
            )
            failure_branch = contract.failure_branch if contract and contract.failure_branch else "已退回"
            self.run_store.append(
                "role_output_validation_failed",
                role=role,
                stage=role,
                output_schema=contract.output_schema if contract else "",
                artifact=contract.artifact if contract else "",
                validation=validation.status,
                schema_errors=validation.schema_errors,
                failure_branch=failure_branch,
            )
            self.run_store.append(
                "validation_failed",
                role=role,
                stage=role,
                contract=contract.name if contract else role,
                output_schema=contract.output_schema if contract else "",
                reason=validation.reason,
                schema_errors=validation.schema_errors,
                failure_branch=failure_branch,
                diagnostic=f"{role} output failed {contract.output_schema if contract else 'role'} validation: {error}",
            )
            self.workflow_state.stage_logs["_self_repair_attempts"] = (
                self.workflow_state.stage_logs.get("_self_repair_attempts", 0) + 1
            )
            self._open_circuit_breaker(
                "role_output_validation_failed",
                stage=role,
                failure_branch=failure_branch,
                schema_errors=validation.schema_errors,
            )
            self.run_store.append(
                "self_repair_attempted",
                role=role,
                cause="role_output_validation_failed",
                action="pause_for_human_after_protocol_failure",
                result="failed",
            )
            self.workflow_state.stage_logs["_human_interventions"] = (
                self.workflow_state.stage_logs.get("_human_interventions", 0) + 1
            )
            failure_types = self.workflow_state.stage_logs.setdefault("_failure_types", {})
            failure_types["protocol"] = failure_types.get("protocol", 0) + 1
            self.state = "已退回"
            self.save_state()
            console.print(f"\n[bold red]{role} 输出协议校验失败[/]，工作流暂停。")
            raise _StopWorkflow() from error

    async def _exec_ops(self, outputs, should_skip, load_artifact):
        """Ops / Release 检查阶段。"""
        if should_skip("已运行检查"):
            outputs["ops"] = load_artifact("ops") or ""
            console.print("[dim]跳过 Ops 阶段（已完成）[/dim]")
            return
        ops_prompt = (
            f"基于以下材料进行发布与运行检查：\n\nPRD:\n{outputs['prd']}\n\n"
            f"实现说明:\n{outputs['implementation']}\n\n验收记录:\n{outputs['acceptance']}"
        )
        while True:
            console.print("\n[bold cyan][Ops][/bold cyan] 正在进行发布与运行检查...")
            ops_result = await self._run_stage(self.ops, ops_prompt, "已运行检查")
            ops_path = self.store.save("ops.md", ops_result)
            self.state = "已运行检查"
            if "已运行检查" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已运行检查")
            self.workflow_state.artifact_paths["ops"] = str(ops_path)
            self.save_state()
            console.print(f"[green]Ops 检查已保存[/]: {ops_path}")
            console.print(Panel(ops_result[:800] + ("..." if len(ops_result) > 800 else ""), title="Ops 检查预览"))
            decision = self.review("Ops 已产出发布与运行检查，是否进入复盘阶段？", ops_result, ops_prompt)
            if decision == "y":
                outputs["ops"] = ops_result
                return
            elif decision == "n":
                raise _StopWorkflow()
            elif decision == "e":
                ops_prompt = self.last_edited_prompt
            elif decision == "r":
                raise _GoBack()

    async def _exec_retro(self, outputs, should_skip, load_artifact):
        """复盘阶段。"""
        if should_skip("已复盘"):
            console.print("[dim]跳过复盘阶段（已完成）[/dim]")
            return
        # 非 ops 模式下，在进入复盘前询问用户
        if not self.enabled("ops"):
            decision = self.review("是否进入复盘阶段？", outputs["acceptance"])
            if decision == "n":
                raise _StopWorkflow()
            elif decision == "r":
                raise _GoBack()
        console.print("\n[bold cyan][PM][/bold cyan] 正在进行复盘...")
        retro_input = (
            f"{RETROSPECTIVE_PROMPT}\n\n"
            f"任务: {self.task}\n\n"
            f"PRD摘要:\n{outputs['prd'][:1000]}\n\n"
            f"验收结论:\n{outputs['acceptance'][:1000]}"
        )
        if outputs["ops"]:
            retro_input += f"\n\nOps 检查:\n{outputs['ops'][:1000]}"
        retro = await self._run_stage(self.pm, retro_input, "已复盘")
        retro_path = self.store.save("retrospective.md", retro)
        self.state = "已复盘"
        if "已复盘" not in self.workflow_state.completed_stages:
            self.workflow_state.completed_stages.append("已复盘")
        self.workflow_state.artifact_paths["retrospective"] = str(retro_path)
        self.save_state()
        console.print(f"[green]复盘记录已保存[/]: {retro_path}")
        console.print(Panel(retro[:800] + ("..." if len(retro) > 800 else ""), title="复盘记录预览"))

    def review(self, stage: str, content: str, current_prompt: str = "") -> str:
        """审查节点：支持 y（继续）、n（终止）、r（退回重做）、e（编辑提示）四种输入。

        Args:
            stage: 阶段描述信息
            content: 当前阶段产出内容
            current_prompt: 当前阶段使用的输入 prompt（用于编辑时展示）

        Returns:
            "y" - 继续执行下一阶段
            "n" - 终止工作流
            "r" - 退回到上一阶段重新执行
            "e" - 编辑提示后重做（编辑后的提示存储在 self.last_edited_prompt）
        """
        if self.auto_confirm:
            console.print(f"[dim]|| {stage} (自动确认)[/dim]")
            self.run_store.append(
                "approval_required",
                stage=stage,
                mode="auto_confirm",
                default_action="continue",
            )
            self.run_store.append(
                "approval_decision",
                stage=stage,
                decision="y",
                actor="auto_confirm",
                result="continued",
            )
            return "y"

        if self.enabled("ceo"):
            # CEO LLM 审查
            self.run_store.append(
                "approval_required",
                stage=stage,
                mode="ceo_review",
                default_action="stop_without_approval",
            )
            console.print(f"\n[bold yellow][CEO][/bold yellow] 正在审查...")
            decision = self.ceo.run(f"审查以下内容并给出决策：\n\n{stage}\n\n{content[:2000]}")
            console.print(Panel(decision, title="CEO 决策", border_style="yellow"))

            if "退回" in decision:
                console.print("[red]CEO 决策：退回，工作流终止[/red]")
                self.run_store.append(
                    "approval_decision",
                    stage=stage,
                    decision="n",
                    actor="ceo",
                    result="stopped",
                )
                return "n"
            elif "需要调整" in decision:
                console.print("[yellow]CEO 建议调整[/yellow]")
                self.run_store.append(
                    "approval_decision",
                    stage=stage,
                    decision="e",
                    actor="ceo",
                    result="needs_prompt_edit",
                )
                return self._prompt_review_input(stage, current_prompt)
            else:  # 批准
                console.print("[green]CEO 决策：批准[/green]")
                self.run_store.append(
                    "approval_decision",
                    stage=stage,
                    decision="y",
                    actor="ceo",
                    result="continued",
                )
                return "y"
        else:
            self.run_store.append(
                "approval_required",
                stage=stage,
                mode="manual_review",
                default_action="stop_without_approval",
            )
            return self._prompt_review_input(stage, current_prompt)

    def _prompt_review_input(self, stage: str, current_prompt: str = "") -> str:
        """提示用户输入审查决策，支持 y/n/r/e 四种输入。

        Args:
            stage: 阶段描述信息
            current_prompt: 当前阶段使用的输入 prompt（用于编辑时展示）
        """
        while True:
            response = input(
                f"\n|| {stage}\n"
                f"   [y] 继续  [n] 终止  [r] 退回重做  [e] 编辑提示: "
            ).strip().lower()
            if response in ("y", "n", "r", "e"):
                break
            console.print("[red]无效输入，请输入 y/n/r/e[/red]")

        if response == "n":
            console.print("[yellow]工作流已终止。[/]")
            self.run_store.append(
                "approval_decision",
                stage=stage,
                decision=response,
                actor="user",
                result="stopped",
            )
        elif response == "r":
            console.print("[yellow]退回到上一阶段重新执行。[/]")
            self.run_store.append(
                "approval_decision",
                stage=stage,
                decision=response,
                actor="user",
                result="rollback_requested",
            )
        elif response == "e":
            # 显示当前 prompt 供用户参考
            if current_prompt:
                preview = current_prompt[:500] + ("..." if len(current_prompt) > 500 else "")
                console.print(Panel(preview, title="当前提示", border_style="cyan"))
            edited = input("|| 请输入修改后的提示（直接回车保留当前提示并追加补充指令）: ").strip()
            if not edited:
                # 用户直接回车，提示输入补充指令
                supplement = input("|| 请输入补充指令: ").strip()
                if supplement:
                    self.last_edited_prompt = current_prompt + "\n\n补充要求：" + supplement
                else:
                    self.last_edited_prompt = current_prompt
            else:
                self.last_edited_prompt = edited
            console.print("[yellow]将使用编辑后的提示重做当前阶段。[/]")
            self.run_store.append(
                "approval_decision",
                stage=stage,
                decision=response,
                actor="user",
                result="prompt_edited",
            )
        else:
            self.run_store.append(
                "approval_decision",
                stage=stage,
                decision=response,
                actor="user",
                result="continued",
            )

        return response

    def confirm(self, message: str) -> bool:
        """人工确认节点（已废弃，保留向后兼容）"""
        return self.review(message, "") == "y"
