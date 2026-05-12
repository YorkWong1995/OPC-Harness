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
from .run_store import RunStore
from .schema import EngineerOutput, QAOutput, parse_role_output
from .store import Store

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
    }
    for log in state.stage_logs.values():
        totals["input_tokens"] += int(log.get("input_tokens", 0) or 0)
        totals["output_tokens"] += int(log.get("output_tokens", 0) or 0)
        totals["duration_seconds"] += float(log.get("duration_seconds", 0) or 0)
        totals["tool_calls"] += int(log.get("tool_calls", 0) or 0)
    totals["duration_seconds"] = round(totals["duration_seconds"], 2)

    metrics = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "task_description": state.task_description,
        "current_stage": state.current_stage,
        "stages": state.stage_logs,
        "totals": totals,
        "artifacts": state.artifact_paths,
    }
    metrics_path = artifacts_dir / "run_metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics_path


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
        self.max_rework_attempts = self.workflow_config.max_rework_attempts
        self.max_rounds = self.workflow_config.max_rounds
        self.run_store = RunStore(self.store.dir)
        self.workflow_state = WorkflowState(task_description=task, run_id=self.run_store.run_id)
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

    def enabled(self, role: str) -> bool:
        """判断可选角色是否启用。"""
        return role in self.roles

    def _run_stage(self, agent, prompt: str, stage_name: str) -> str:
        """运行 agent 并记录耗时和 token 到 stage_logs。"""
        self.run_store.append("stage_started", stage=stage_name, role=getattr(agent, "role", stage_name), prompt=prompt)
        start = time.monotonic()
        result = agent.run(prompt)
        duration = time.monotonic() - start
        self._record_stage_metrics(agent, stage_name, duration)
        self.run_store.append(
            "stage_completed",
            stage=stage_name,
            role=getattr(agent, "role", stage_name),
            duration_seconds=round(duration, 2),
            input_tokens=getattr(agent, "last_input_tokens", 0),
            output_tokens=getattr(agent, "last_output_tokens", 0),
            tool_calls=getattr(agent, "last_tool_calls", 0),
            output=result,
        )
        return result

    def _record_stage_metrics(self, agent, stage_name: str, duration: float):
        input_tokens = getattr(agent, "last_input_tokens", 0)
        output_tokens = getattr(agent, "last_output_tokens", 0)
        tool_calls = getattr(agent, "last_tool_calls", 0)
        self.workflow_state.stage_logs[stage_name] = {
            "input_tokens": int(input_tokens) if isinstance(input_tokens, (int, float)) else 0,
            "output_tokens": int(output_tokens) if isinstance(output_tokens, (int, float)) else 0,
            "duration_seconds": round(duration, 2),
            "tool_calls": int(tool_calls) if isinstance(tool_calls, (int, float)) else 0,
        }

    async def _run_stages_parallel(self, stage_specs: list[tuple[object, str, str]]) -> list[str]:
        async def run_one(agent, prompt: str, stage_name: str) -> str:
            start = time.monotonic()
            result = await asyncio.to_thread(agent.run, prompt)
            self._record_stage_metrics(agent, stage_name, time.monotonic() - start)
            return result

        return await asyncio.gather(*(run_one(*spec) for spec in stage_specs))

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

    def run(self, resume_from: str | None = None):
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
            self.run_store = RunStore(self.store.dir, self.workflow_state.run_id or None)
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

        # 构建活跃阶段列表
        active_stages: list[str] = []
        if self.enabled("growth") and self.enabled("architect"):
            active_stages.extend(["pm", "growth_architect"])
        else:
            if self.enabled("growth"):
                active_stages.append("growth")
            active_stages.append("pm")
            if self.enabled("architect"):
                active_stages.append("architect")
        active_stages.append("engineer")
        active_stages.append("qa")
        if self.enabled("ops"):
            active_stages.append("ops")
        active_stages.append("retro")

        stage_idx = 0
        rounds = 0
        while stage_idx < len(active_stages):
            rounds += 1
            if rounds > self.max_rounds:
                self.state = "已退回"
                self.run_store.append("workflow_stopped", reason="max_rounds_exceeded", max_rounds=self.max_rounds)
                self.save_state()
                return
            current = active_stages[stage_idx]
            try:
                self._run_stage_by_name(current, outputs, should_skip, load_artifact)
                stage_idx += 1
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
                    self.save_state()
                    stage_idx -= 1
                    console.print(f"[yellow]退回到上一阶段: {prev}[/yellow]")
                else:
                    # 第一个阶段无法退回，清除已完成标记后重做当前阶段
                    cur_state_name = self._stage_to_state_name(current)
                    if cur_state_name in self.workflow_state.completed_stages:
                        self.workflow_state.completed_stages.remove(cur_state_name)
                    self.save_state()
                    console.print("[yellow]已经是第一个阶段，将重做当前阶段。[/yellow]")
            except _StopWorkflow:
                return

        console.print("\n[bold green]工作流完成！[/] 所有产物已保存到 artifacts/ 目录。")
        metrics_path = generate_metrics(self.workflow_state, self.store.dir)
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
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

    def _run_stage_by_name(self, stage: str, outputs: dict, should_skip, load_artifact):
        """根据阶段名执行对应逻辑。完成后更新 outputs 字典。"""
        if stage == "growth":
            self._exec_growth(outputs, should_skip, load_artifact)
        elif stage == "pm":
            self._exec_pm(outputs, should_skip, load_artifact)
        elif stage == "growth_architect":
            self._exec_growth_architect_parallel(outputs, should_skip, load_artifact)
        elif stage == "architect":
            self._exec_architect(outputs, should_skip, load_artifact)
        elif stage == "engineer":
            self._exec_engineer(outputs, should_skip, load_artifact)
        elif stage == "qa":
            self._exec_qa(outputs, should_skip, load_artifact)
        elif stage == "ops":
            self._exec_ops(outputs, should_skip, load_artifact)
        elif stage == "retro":
            self._exec_retro(outputs, should_skip, load_artifact)

    def _exec_growth_architect_parallel(self, outputs, should_skip, load_artifact):
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
        results = asyncio.run(self._run_stages_parallel(specs))
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

    def _exec_growth(self, outputs, should_skip, load_artifact):
        """Growth / Research 阶段。"""
        if should_skip("已调研"):
            outputs["growth"] = load_artifact("growth") or ""
            console.print("[dim]跳过 Growth 阶段（已完成）[/dim]")
            return
        growth_prompt = f"基于以下任务产出 Growth / Research 建议：\n\n{self.task}"
        while True:
            console.print("\n[bold cyan][Growth][/bold cyan] 正在产出研究建议...")
            growth = self._run_stage(self.growth, growth_prompt, "已调研")
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

    def _exec_pm(self, outputs, should_skip, load_artifact):
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
            prd = self._run_stage(self.pm, prd_prompt, "已定义")
            prd_path = self.store.save("prd.md", prd)
            self._parse_role_output("pm", prd)
            self.state = "已定义"
            if "已定义" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已定义")
            self.workflow_state.artifact_paths["prd"] = str(prd_path)
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

    def _exec_architect(self, outputs, should_skip, load_artifact):
        """Architect 产出架构方案阶段。"""
        if should_skip("已设计"):
            outputs["architecture"] = load_artifact("architecture") or ""
            console.print("[dim]跳过 Architect 阶段（已完成）[/dim]")
            return
        arch_prompt = f"基于以下 PRD 产出架构方案：\n\n{outputs['prd']}"
        while True:
            console.print("\n[bold cyan][Architect][/bold cyan] 正在基于 PRD 产出架构方案...")
            architecture = self._run_stage(self.architect, arch_prompt, "已设计")
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

    def _exec_engineer(self, outputs, should_skip, load_artifact):
        """Engineer 实现阶段。"""
        if should_skip("实现中"):
            outputs["implementation"] = load_artifact("implementation") or ""
            console.print("[dim]跳过 Engineer 阶段（已完成）[/dim]")
            return
        if outputs["architecture"]:
            engineer_input = f"基于以下 PRD 和架构方案完成实现：\n\nPRD:\n{outputs['prd']}\n\n架构方案:\n{outputs['architecture']}"
        else:
            engineer_input = f"基于以下 PRD 完成实现：\n\n{outputs['prd']}"
        eng_prompt = engineer_input
        while True:
            console.print("\n[bold cyan][Engineer][/bold cyan] 正在实现...")
            implementation = self._run_stage(self.engineer, eng_prompt, "实现中")
            impl_path = self.store.save("implementation.md", implementation)
            engineer_output = self._parse_role_output("engineer", implementation)
            self.state = "实现中"
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

    def _exec_qa(self, outputs, should_skip, load_artifact):
        """QA 验收阶段。"""
        if should_skip("待验收") and should_skip("已通过"):
            outputs["acceptance"] = load_artifact("acceptance") or ""
            console.print("[dim]跳过 QA 阶段（已完成）[/dim]")
            return
        console.print("\n[bold cyan][QA][/bold cyan] 正在基于验收标准检查实现...")
        acceptance = self._run_stage(self.qa,
            f"验证以下实现是否满足 PRD 要求：\n\nPRD:\n{outputs['prd']}\n\n实现说明:\n{outputs['implementation']}",
            "待验收",
        )
        acc_path = self.store.save("acceptance.md", acceptance)
        self.state = "待验收"
        if "待验收" not in self.workflow_state.completed_stages:
            self.workflow_state.completed_stages.append("待验收")
        self.workflow_state.artifact_paths["acceptance"] = str(acc_path)
        self.save_state()
        console.print(f"[green]验收记录已保存[/]: {acc_path}")
        console.print(Panel(acceptance[:800] + ("..." if len(acceptance) > 800 else ""), title="验收记录预览"))

        # 判断验收结果
        qa_output = self._parse_role_output("qa", acceptance)
        qa_failed = qa_output.status == "fail" if isinstance(qa_output, QAOutput) else "不通过" in acceptance
        if qa_failed:
            self.workflow_state.rework_attempts += 1
            self.state = "已退回"
            if "已退回" not in self.workflow_state.completed_stages:
                self.workflow_state.completed_stages.append("已退回")
            self.run_store.append(
                "qa_failed",
                rework_attempts=self.workflow_state.rework_attempts,
                defects=qa_output.defects if isinstance(qa_output, QAOutput) else [acceptance],
            )
            self.save_state()
            if self.workflow_state.rework_attempts > self.max_rework_attempts:
                console.print("\n[bold red]QA 验收未通过且超过最大返工次数[/]，工作流暂停。")
                raise _StopWorkflow()
            outputs["implementation"] = self._run_rework(outputs, acceptance)
            return self._exec_qa(outputs, should_skip, load_artifact)

        self.state = "已通过"
        if "已通过" not in self.workflow_state.completed_stages:
            self.workflow_state.completed_stages.append("已通过")
        self.save_state()
        console.print("\n[bold green]QA 验收通过[/]")
        outputs["acceptance"] = acceptance

    def _run_rework(self, outputs: dict, acceptance: str) -> str:
        rework_prompt = (
            "QA 验收未通过，请根据缺陷修正实现并输出新的实现说明：\n\n"
            f"PRD:\n{outputs['prd']}\n\n上一轮实现说明:\n{outputs['implementation']}\n\nQA 缺陷:\n{acceptance}"
        )
        console.print("\n[bold cyan][Engineer][/bold cyan] 正在根据 QA 缺陷返工...")
        implementation = self._run_stage(self.engineer, rework_prompt, "实现中")
        impl_path = self.store.save("implementation.md", implementation)
        self._parse_role_output("engineer", implementation)
        self.workflow_state.artifact_paths["implementation"] = str(impl_path)
        self.state = "实现中"
        self.save_state()
        return implementation

    def _parse_role_output(self, role: str, content: str):
        try:
            parsed = parse_role_output(role, content)
            self.run_store.append("role_output_validated", role=role)
            return parsed
        except Exception as error:
            self.run_store.append("role_output_validation_failed", role=role, error=str(error))
            return None

    def _exec_ops(self, outputs, should_skip, load_artifact):
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
            ops_result = self._run_stage(self.ops, ops_prompt, "已运行检查")
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

    def _exec_retro(self, outputs, should_skip, load_artifact):
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
        retro = self._run_stage(self.pm, retro_input, "已复盘")
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
            return "y"

        if self.enabled("ceo"):
            # CEO LLM 审查
            console.print(f"\n[bold yellow][CEO][/bold yellow] 正在审查...")
            decision = self.ceo.run(f"审查以下内容并给出决策：\n\n{stage}\n\n{content[:2000]}")
            console.print(Panel(decision, title="CEO 决策", border_style="yellow"))

            if "退回" in decision:
                console.print("[red]CEO 决策：退回，工作流终止[/red]")
                return "n"
            elif "需要调整" in decision:
                console.print("[yellow]CEO 建议调整[/yellow]")
                return self._prompt_review_input(stage, current_prompt)
            else:  # 批准
                console.print("[green]CEO 决策：批准[/green]")
                return "y"
        else:
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
        elif response == "r":
            console.print("[yellow]退回到上一阶段重新执行。[/]")
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

        return response

    def confirm(self, message: str) -> bool:
        """人工确认节点（已废弃，保留向后兼容）"""
        return self.review(message, "") == "y"
