"""Harness 工作流状态机：驱动 PM → Engineer → QA 的最小闭环"""

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
    RETROSPECTIVE_PROMPT,
)
from .store import Store

console = Console()

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
    ):
        self.task = task
        self.project_dir = project_dir.resolve()
        self.store = Store(self.project_dir / "artifacts")
        self.state = "待澄清"
        self.auto_confirm = auto_confirm
        self.roles = roles or set()  # 默认为空集合，不强制添加角色
        if ceo_review:
            self.roles.add("ceo")
        if skip_architect:
            self.roles.discard("architect")
        self.model = model
        self.use_embedded_engineer = use_embedded_engineer

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

    def run(self):
        console.print(Panel(f"[bold]任务[/]: {self.task}", title="OPC Harness 工作流启动"))

        pm_input = self.task

        # ---- Step 0: Growth / Research 调研（可选）----
        growth = None
        if self.enabled("growth"):
            console.print("\n[bold cyan][Growth][/bold cyan] 正在产出研究建议...")
            growth = self.growth.run(f"基于以下任务产出 Growth / Research 建议：\n\n{self.task}")
            growth_path = self.store.save("growth.md", growth)
            self.state = "已调研"
            console.print(f"[green]研究建议已保存[/]: {growth_path}")
            console.print(Panel(growth[:800] + ("..." if len(growth) > 800 else ""), title="研究建议预览"))
            if not self.review("Growth 已产出研究建议，是否继续让 PM 产出 PRD？", growth):
                return
            pm_input = f"基于以下任务和 Growth 建议产出 PRD：\n\n任务：\n{self.task}\n\nGrowth 建议：\n{growth}"

        # ---- Step 1: PM 产出 PRD ----
        console.print("\n[bold cyan][PM][/bold cyan] 正在产出 PRD...")
        prd = self.pm.run(pm_input)
        prd_path = self.store.save("prd.md", prd)
        self.state = "已定义"
        console.print(f"[green]PRD 已保存[/]: {prd_path}")
        console.print(Panel(prd[:800] + ("..." if len(prd) > 800 else ""), title="PRD 预览"))
        if not self.review("PM 已产出 PRD，是否继续？", prd):
            return

        # ---- Step 2: Architect 产出架构方案（可选）----
        if self.enabled("architect"):
            console.print("\n[bold cyan][Architect][/bold cyan] 正在基于 PRD 产出架构方案...")
            architecture = self.architect.run(f"基于以下 PRD 产出架构方案：\n\n{prd}")
            arch_path = self.store.save("architecture.md", architecture)
            self.state = "已设计"
            console.print(f"[green]架构说明已保存[/]: {arch_path}")
            console.print(
                Panel(architecture[:800] + ("..." if len(architecture) > 800 else ""), title="架构说明预览")
            )
            if not self.review("Architect 已产出架构方案，是否继续让 Engineer 实现？", architecture):
                return
            engineer_input = f"基于以下 PRD 和架构方案完成实现：\n\nPRD:\n{prd}\n\n架构方案:\n{architecture}"
        else:
            console.print("\n[dim]跳过 Architect 环节[/dim]")
            engineer_input = f"基于以下 PRD 完成实现：\n\n{prd}"

        # ---- Step 3: Engineer 实现 ----
        console.print("\n[bold cyan][Engineer][/bold cyan] 正在实现...")
        implementation = self.engineer.run(engineer_input)
        impl_path = self.store.save("implementation.md", implementation)
        self.state = "实现中"
        console.print(f"[green]实现说明已保存[/]: {impl_path}")
        console.print(Panel(implementation[:800] + ("..." if len(implementation) > 800 else ""), title="实现说明预览"))
        if not self.review("Engineer 已完成实现，是否继续让 QA 验收？", implementation):
            return

        # ---- Step 4: QA 验收 ----
        console.print("\n[bold cyan][QA][/bold cyan] 正在基于验收标准检查实现...")
        acceptance = self.qa.run(
            f"验证以下实现是否满足 PRD 要求：\n\nPRD:\n{prd}\n\n实现说明:\n{implementation}"
        )
        acc_path = self.store.save("acceptance.md", acceptance)
        self.state = "待验收"
        console.print(f"[green]验收记录已保存[/]: {acc_path}")
        console.print(Panel(acceptance[:800] + ("..." if len(acceptance) > 800 else ""), title="验收记录预览"))

        # ---- Step 5: 判断验收结果 ----
        if "不通过" in acceptance:
            self.state = "已退回"
            console.print("\n[bold red]QA 验收未通过[/]，工作流暂停。请查看 acceptance.md 了解原因。")
            return

        self.state = "已通过"
        console.print("\n[bold green]QA 验收通过[/]")

        # ---- Step 6: Ops / Release 检查（可选）----
        ops_result = None
        if self.enabled("ops"):
            console.print("\n[bold cyan][Ops][/bold cyan] 正在进行发布与运行检查...")
            ops_result = self.ops.run(
                f"基于以下材料进行发布与运行检查：\n\nPRD:\n{prd}\n\n实现说明:\n{implementation}\n\n验收记录:\n{acceptance}"
            )
            ops_path = self.store.save("ops.md", ops_result)
            self.state = "已运行检查"
            console.print(f"[green]Ops 检查已保存[/]: {ops_path}")
            console.print(Panel(ops_result[:800] + ("..." if len(ops_result) > 800 else ""), title="Ops 检查预览"))
            if not self.review("Ops 已产出发布与运行检查，是否进入复盘阶段？", ops_result):
                return
        elif not self.review("是否进入复盘阶段？", acceptance):
            return

        # ---- Step 7: 复盘 ----
        console.print("\n[bold cyan][PM][/bold cyan] 正在进行复盘...")
        retro_input = (
            f"{RETROSPECTIVE_PROMPT}\n\n"
            f"任务: {self.task}\n\n"
            f"PRD摘要:\n{prd[:1000]}\n\n"
            f"验收结论:\n{acceptance[:1000]}"
        )
        if ops_result:
            retro_input += f"\n\nOps 检查:\n{ops_result[:1000]}"
        retro = self.pm.run(retro_input)
        retro_path = self.store.save("retrospective.md", retro)
        self.state = "已复盘"
        console.print(f"[green]复盘记录已保存[/]: {retro_path}")
        console.print(Panel(retro[:800] + ("..." if len(retro) > 800 else ""), title="复盘记录预览"))

        console.print("\n[bold green]工作流完成！[/] 所有产物已保存到 artifacts/ 目录。")

    def review(self, stage: str, content: str) -> bool:
        """审查节点：根据配置选择人工确认或 CEO 审查"""
        if self.auto_confirm:
            console.print(f"[dim]|| {stage} (自动确认)[/dim]")
            return True

        if self.enabled("ceo"):
            # CEO LLM 审查
            console.print(f"\n[bold yellow][CEO][/bold yellow] 正在审查...")
            decision = self.ceo.run(f"审查以下内容并给出决策：\n\n{stage}\n\n{content[:2000]}")
            console.print(Panel(decision, title="CEO 决策", border_style="yellow"))

            if "退回" in decision:
                console.print("[red]CEO 决策：退回，工作流终止[/red]")
                return False
            elif "需要调整" in decision:
                response = input(f"\n|| CEO 建议调整，是否继续？(y/n): ").strip().lower()
                if response != "y":
                    console.print("[yellow]工作流已暂停。[/]")
                    return False
                return True
            else:  # 批准
                console.print("[green]CEO 决策：批准[/green]")
                return True
        else:
            # 人工确认（现有逻辑）
            response = input(f"\n|| {stage} (y/n): ").strip().lower()
            if response != "y":
                console.print("[yellow]工作流已暂停。[/]")
                return False
            return True

    def confirm(self, message: str) -> bool:
        """人工确认节点（已废弃，保留向后兼容）"""
        return self.review(message, "")
