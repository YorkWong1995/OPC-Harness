"""OPC CLI 入口"""

import argparse
import asyncio
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .workflow import HarnessWorkflow, WorkflowState
from .run_store import RunStore, aggregate_run_cost_trend, find_run_artifacts, summarize_run, trace_inspect, trace_summary
from .config import (
    ALL_OPTIONAL_ROLES,
    load_project_config,
    load_workflow_config,
    normalize_roles,
    validate_project_config,
)
from .knowledge.index_paths import get_index_root, get_workspace_root
from .generation.templates import TemplateRenderError, build_project_template_variables, render_template_directory
from .project_types import ProjectTypeDefinition, load_project_type_registry
from .tools.qt_tools import QtEnvironmentCheckResult, check_qt_environment, format_qt_environment_report

console = Console()


def main():
    # Windows 终端 UTF-8 支持
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="OPC - 单人软件公司 AI 系统",
        prog="opc",
    )
    parser.add_argument("--version", action="version", version=f"opc {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # ---- opc run "任务描述" ----
    run_parser = subparsers.add_parser("run", help="运行 harness 工作流")
    run_parser.add_argument("task", help="任务描述")
    run_parser.add_argument(
        "--project",
        default=None,
        help="项目名称，自动在 workspace/ 下创建对应目录",
    )
    run_parser.add_argument(
        "--project-dir",
        default=None,
        help="项目目录（指定已有目录，与 --project 二选一）",
    )
    run_parser.add_argument(
        "--model",
        default=None,
        help="模型名称（默认读取 ANTHROPIC_MODEL 环境变量，否则 claude-sonnet-4-6）",
    )
    run_parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="自动确认所有节点（跳过人工审批）",
    )
    run_parser.add_argument(
        "--ceo-review",
        action="store_true",
        help="启用 CEO LLM 审查（智能审查 + 人工最终决策）",
    )
    run_parser.add_argument(
        "--skip-architect",
        action="store_true",
        help="跳过 Architect 环节（适用于简单任务）",
    )
    run_parser.add_argument(
        "--with-architect",
        action="store_true",
        help="显式启用 Architect 环节",
    )
    run_parser.add_argument(
        "--with-ops",
        action="store_true",
        help="显式启用 Ops 环节",
    )
    run_parser.add_argument(
        "--with-growth",
        action="store_true",
        help="显式启用 Growth/Research 环节",
    )
    run_parser.add_argument(
        "--resume-from",
        default=None,
        help="从指定阶段恢复执行（跳过已完成阶段），如 '已定义'、'实现中'",
    )
    run_parser.add_argument(
        "--profile",
        default=None,
        help="使用指定的 profile 配置（覆盖 opc.toml 中的默认 profile）",
    )

    # ---- opc resume ----
    resume_parser = subparsers.add_parser("resume", help="从上次中断处恢复工作流执行")
    resume_parser.add_argument(
        "--project",
        default=None,
        help="项目名称（workspace/ 下的目录）",
    )
    resume_parser.add_argument(
        "--project-dir",
        default=None,
        help="项目目录（指定已有目录，与 --project 二选一）",
    )
    resume_parser.add_argument(
        "--model",
        default=None,
        help="模型名称",
    )
    resume_parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="自动确认所有节点",
    )

    # ---- opc index ----
    index_parser = subparsers.add_parser("index", help="构建知识索引")
    index_parser.add_argument("--name", required=True, help="索引名称")
    index_parser.add_argument("--dirs", nargs="+", required=True, help="要索引的目录或文件")
    index_parser.add_argument("--extensions", nargs="*", help="文件扩展名过滤（如 .py .md）")
    index_parser.add_argument("--overwrite", action="store_true", help="覆盖已有索引")
    index_parser.add_argument("--incremental", action="store_true", help="增量更新已有索引，仅重建变更文件")
    index_parser.add_argument("--verbose", action="store_true", help="详细输出")

    # ---- opc query ----
    query_parser = subparsers.add_parser("query", help="知识检索查询")
    query_parser.add_argument("question", help="查询问题")
    query_parser.add_argument("--name", required=True, help="索引名称")
    query_parser.add_argument("--top-k", type=int, default=10, help="返回结果数（默认 10）")
    query_parser.add_argument("--no-llm", action="store_true", help="不调用 LLM 生成答案，仅显示检索结果")
    query_parser.add_argument("--model", default=None, help="覆盖 LLM 模型")

    # ---- opc generate qt ----
    generate_parser = subparsers.add_parser("generate", help="生成项目模板")
    generate_subparsers = generate_parser.add_subparsers(dest="generate_command")
    generate_qt_parser = generate_subparsers.add_parser("qt", help="生成 Qt Widgets CMake 项目")
    generate_qt_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    generate_qt_parser.add_argument("--name", required=True, help="项目名称")
    generate_qt_parser.add_argument("--target-dir", required=True, help="目标目录")
    generate_qt_parser.add_argument("--template", default="widgets-cmake", help="模板 id（默认 widgets-cmake）")
    generate_qt_parser.add_argument("--class-name", default="MainWindow", help="主窗口类名")
    generate_qt_parser.add_argument("--dry-run", action="store_true", help="只显示将写入文件，不创建文件")

    # ---- opc project-types list ----
    project_types_parser = subparsers.add_parser("project-types", help="查看可用项目类型")
    project_types_subparsers = project_types_parser.add_subparsers(dest="project_types_command")
    project_types_list_parser = project_types_subparsers.add_parser("list", help="列出已启用项目类型")
    project_types_list_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    project_types_list_parser.add_argument("--json", action="store_true", help="输出 JSON")

    # ---- opc task ----
    task_parser = subparsers.add_parser("task", help="查看 markdown 任务清单")
    task_subparsers = task_parser.add_subparsers(dest="task_command")
    task_list_parser = task_subparsers.add_parser("list", help="列出任务清单")
    task_list_parser.add_argument("--tasks", type=Path, default=Path("tasks.md"), help="任务清单路径")
    task_list_parser.add_argument("--all", action="store_true", help="显示已完成任务")
    task_status_parser = task_subparsers.add_parser("status", help="显示任务统计")
    task_status_parser.add_argument("--tasks", type=Path, default=Path("tasks.md"), help="任务清单路径")

    # ---- opc memory ----
    memory_parser = subparsers.add_parser("memory", help="管理长期 memory")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command")
    memory_list_parser = memory_subparsers.add_parser("list", help="列出长期 memory")
    memory_list_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    memory_list_parser.add_argument("--scope", choices=["user", "project", "workflow"], default=None, help="按 scope 过滤")
    memory_list_parser.add_argument("--json", action="store_true", help="输出 JSON")
    memory_add_parser = memory_subparsers.add_parser("add", help="写入长期 memory")
    memory_add_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    memory_add_parser.add_argument("--scope", choices=["user", "project", "workflow"], required=True, help="memory scope")
    memory_add_parser.add_argument("--content", required=True, help="memory 内容")
    memory_add_parser.add_argument("--source", required=True, help="来源说明")
    memory_add_parser.add_argument("--confidence", type=float, default=1.0, help="置信度")
    memory_add_parser.add_argument("--expires-at", default="", help="ISO 过期时间")
    memory_add_parser.add_argument("--confirm", action="store_true", help="确认写入长期 memory")
    memory_delete_parser = memory_subparsers.add_parser("delete", help="删除长期 memory")
    memory_delete_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    memory_delete_parser.add_argument("--id", required=True, help="memory id")
    memory_delete_parser.add_argument("--confirm", action="store_true", help="确认删除")
    memory_supersede_parser = memory_subparsers.add_parser("supersede", help="用新 memory 替代旧 memory")
    memory_supersede_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    memory_supersede_parser.add_argument("--id", required=True, help="被替代的 memory id")
    memory_supersede_parser.add_argument("--content", required=True, help="新 memory 内容")
    memory_supersede_parser.add_argument("--source", required=True, help="来源说明")
    memory_supersede_parser.add_argument("--scope", choices=["user", "project", "workflow"], default=None, help="新 memory scope，默认沿用旧 scope")
    memory_supersede_parser.add_argument("--confidence", type=float, default=1.0, help="置信度")
    memory_supersede_parser.add_argument("--expires-at", default="", help="ISO 过期时间")
    memory_supersede_parser.add_argument("--confirm", action="store_true", help="确认替代")
    memory_gc_parser = memory_subparsers.add_parser("gc", help="检查过期和重复 memory")
    memory_gc_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    memory_gc_parser.add_argument("--confirm", action="store_true", help="确认删除过期和重复 memory")

    # ---- opc index-list ----
    subparsers.add_parser("index-list", help="列出所有已有索引")

    # ---- opc index-delete ----
    del_parser = subparsers.add_parser("index-delete", help="删除索引")
    del_parser.add_argument("--name", required=True, help="索引名称")

    # ---- opc runs list ----
    runs_parser = subparsers.add_parser("runs", help="查看历史运行记录")
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command")
    runs_list_parser = runs_subparsers.add_parser("list", help="列出 run 记录")
    runs_list_parser.add_argument("--root", default=None, help="搜索根目录（默认 workspace）")
    runs_list_parser.add_argument("--project-dir", default=None, help="仅查看指定项目目录")
    runs_cost_parser = runs_subparsers.add_parser("cost", help="查看 run 成本趋势")
    runs_cost_parser.add_argument("--root", default=None, help="搜索根目录（默认 workspace）")
    runs_cost_parser.add_argument("--project-dir", default=None, help="仅查看指定项目目录")
    runs_cost_parser.add_argument("--limit", type=int, default=10, help="最近 N 次 run")

    # ---- opc trace show / summary ----
    trace_parser = subparsers.add_parser("trace", help="查看 run trace")
    trace_subparsers = trace_parser.add_subparsers(dest="trace_command")
    trace_show_parser = trace_subparsers.add_parser("show", help="显示 run 事件")
    trace_show_parser.add_argument("--artifacts-dir", required=True, help="artifacts 目录")
    trace_show_parser.add_argument("--limit", type=int, default=20, help="显示最近 N 条事件")
    trace_summary_parser = trace_subparsers.add_parser("summary", help="显示 trace 摘要")
    trace_summary_parser.add_argument("--artifacts-dir", required=True, help="artifacts 目录")
    trace_inspect_parser = trace_subparsers.add_parser("inspect", help="只读诊断 run trace")
    trace_inspect_parser.add_argument("--artifacts-dir", required=True, help="artifacts 目录")
    trace_inspect_parser.add_argument("--json", action="store_true", help="输出 JSON")
    trace_inspect_parser.add_argument(
        "--focus",
        choices=["all", "timeline", "artifacts", "tool_calls", "decisions", "failures", "metrics", "compatibility"],
        default="all",
        help="聚焦显示某类 inspect 数据",
    )

    # ---- opc config validate ----
    config_parser = subparsers.add_parser("config", help="管理 OPC 配置")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_validate_parser = config_subparsers.add_parser("validate", help="校验 opc.toml")
    config_validate_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    config_validate_parser.add_argument("--profile", default=None, help="指定要校验的 profile")

    # ---- opc init ----
    init_parser = subparsers.add_parser("init", help="初始化 opc.toml")
    init_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    init_parser.add_argument("--force", action="store_true", help="覆盖已有 opc.toml")

    # ---- opc doctor ----
    doctor_parser = subparsers.add_parser("doctor", help="检查 OPC 本地使用环境")
    doctor_parser.add_argument("--project-dir", default=".", help="项目目录（默认当前目录）")
    doctor_parser.add_argument("--profile", default=None, help="指定要检查的 profile")

    # ---- opc ui ----
    ui_parser = subparsers.add_parser("ui", help="启动 Streamlit 可视化控制台")
    ui_parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    ui_parser.add_argument("--port", type=int, default=8501, help="监听端口（默认 8501）")

    args = parser.parse_args()

    if args.command == "run":
        _run_workflow(args)
    elif args.command == "resume":
        _run_resume(args)
    elif args.command == "index":
        _run_index(args)
    elif args.command == "query":
        _run_query(args)
    elif args.command == "generate":
        _run_generate(args)
    elif args.command == "project-types":
        _run_project_types(args)
    elif args.command == "task":
        _run_task(args)
    elif args.command == "memory":
        _run_memory(args)
    elif args.command == "index-list":
        _run_index_list(args)
    elif args.command == "index-delete":
        _run_index_delete(args)
    elif args.command == "runs":
        _run_runs(args)
    elif args.command == "trace":
        _run_trace(args)
    elif args.command == "config":
        _run_config(args)
    elif args.command == "init":
        _run_init(args)
    elif args.command == "doctor":
        _run_doctor(args)
    elif args.command == "ui":
        _run_ui(args)
    else:
        parser.print_help()


def _get_workspace_root() -> Path:
    """获取 workspace 根目录"""
    return get_workspace_root()


def _get_index_root(name: str) -> Path:
    """获取索引根目录

    支持通过环境变量 OPC_INDEX_ROOT 覆盖默认位置，
    C 盘空间受限场景可设置为 D:/opc_index
    """
    return get_index_root(name)


# ---- opc run ----

def _run_workflow(args):
    # 确定项目目录：--project 优先，其次 --project-dir，最后当前目录
    if args.project:
        opc_root = Path(__file__).resolve().parent.parent.parent
        project_dir = opc_root / "workspace" / args.project
        project_dir.mkdir(parents=True, exist_ok=True)
    elif args.project_dir:
        project_dir = Path(args.project_dir)
        if not project_dir.exists():
            print(f"错误：项目目录不存在 {project_dir}")
            return
    else:
        project_dir = Path(".")

    config = load_workflow_config(project_dir, profile=args.profile)
    roles = normalize_roles(config.roles)

    if args.ceo_review or config.ceo_review:
        roles.add("ceo")

    if args.with_architect:
        roles.add("architect")
    if args.with_ops:
        roles.add("ops")
    if args.with_growth:
        roles.add("growth")

    if args.skip_architect:
        roles.discard("architect")
        if "all" in config.roles:
            roles = set(ALL_OPTIONAL_ROLES)
            roles.discard("architect")

    auto_confirm = args.auto_confirm or config.auto_confirm

    workflow = HarnessWorkflow(
        task=args.task,
        project_dir=project_dir,
        auto_confirm=auto_confirm,
        roles=roles,
        model=args.model,
        profile=config.profile,
    )
    asyncio.run(workflow.run(resume_from=args.resume_from))


# ---- opc resume ----

def _run_resume(args):
    """从上次中断处恢复工作流执行"""
    if args.project:
        opc_root = Path(__file__).resolve().parent.parent.parent
        project_dir = opc_root / "workspace" / args.project
    elif args.project_dir:
        project_dir = Path(args.project_dir)
    else:
        project_dir = Path(".")

    artifacts_dir = project_dir / "artifacts"
    state_path = artifacts_dir / ".opc_state.json"

    if not state_path.exists():
        console.print("[red]错误：未找到可恢复的工作流状态。[/red]")
        console.print(f"[dim]查找路径: {state_path}[/dim]")
        return

    try:
        saved_state = WorkflowState.load_state(artifacts_dir)
    except Exception as e:
        console.print(f"[red]错误：无法加载工作流状态: {e}[/red]")
        return

    console.print(Panel(
        f"[bold]任务[/]: {saved_state.task_description}\n"
        f"[bold]Run ID[/]: {saved_state.run_id}\n"
        f"[bold]当前阶段[/]: {saved_state.current_stage}\n"
        f"[bold]已完成[/]: {' → '.join(saved_state.completed_stages) if saved_state.completed_stages else '无'}",
        title="检测到中断的工作流",
    ))

    config = load_workflow_config(project_dir)
    roles = normalize_roles(config.roles)
    auto_confirm = args.auto_confirm or config.auto_confirm

    workflow = HarnessWorkflow(
        task=saved_state.task_description,
        project_dir=project_dir,
        auto_confirm=auto_confirm,
        roles=roles,
        model=args.model,
        profile=config.profile,
    )
    asyncio.run(workflow.run(resume_from=saved_state.current_stage))


# ---- opc index ----

def _run_index(args):
    from .knowledge.indexer import Indexer

    index_root = _get_index_root(args.name)
    source_dirs = [Path(d).resolve() for d in args.dirs]

    # 验证目录存在
    for d in source_dirs:
        if not d.exists():
            console.print(f"[red]错误：路径不存在 {d}[/red]")
            return

    extensions = args.extensions if args.extensions else None

    console.print(Panel(
        f"[bold]索引名称[/]: {args.name}\n"
        f"[bold]源目录[/]: {', '.join(str(d) for d in source_dirs)}\n"
        f"[bold]扩展名过滤[/]: {', '.join(extensions) if extensions else '全部支持'}",
        title="OPC 知识索引构建",
    ))

    indexer = Indexer(args.name, index_root)
    meta = indexer.build(
        source_dirs=source_dirs,
        extensions=extensions,
        overwrite=args.overwrite,
        verbose=True,
        incremental=args.incremental,
    )

    console.print(Panel(
        f"[bold green]索引构建完成[/]\n\n"
        f"索引名称: {meta.index_name}\n"
        f"文件数: {meta.total_files}\n"
        f"分块数: {meta.total_chunks}\n"
        f"Embedding: {meta.embedding_model}\n"
        f"索引位置: {index_root}",
        title="索引摘要",
    ))


# ---- opc query ----

def _run_query(args):
    from .knowledge.indexer import Indexer
    from .knowledge.bm25_index import BM25Index
    from .knowledge.vector_store import VectorStore
    from .knowledge.retriever import Retriever
    from .knowledge.answer import AnswerGenerator

    index_root = _get_index_root(args.name)

    # 检查索引是否存在
    meta = Indexer.load_meta(index_root)
    if meta is None:
        console.print(f"[red]错误：索引 '{args.name}' 不存在。请先运行 opc index --name {args.name}[/red]")
        return

    # 加载索引
    console.print("[dim]加载索引...[/dim]")
    bm25 = BM25Index()
    bm25.load(index_root / "bm25")

    vs = VectorStore(index_root / "vector")
    vs.create_collection(args.name)

    retriever = Retriever(vs, bm25, meta.file_dependencies)

    # 检索
    console.print(f"\n[bold]查询:[/] {args.question}")
    console.print("[dim]检索中...[/dim]")
    results = retriever.retrieve(args.question, top_k=args.top_k)

    if not results:
        console.print("[yellow]未找到相关结果[/yellow]")
        return

    # 显示检索结果
    table = Table(title="检索结果", show_lines=True)
    table.add_column("#", style="bold", width=3)
    table.add_column("来源", width=40)
    table.add_column("RRF分数", width=10)
    table.add_column("向量排名", width=8)
    table.add_column("BM25排名", width=8)
    table.add_column("预览", width=50)

    for i, r in enumerate(results, 1):
        preview = r.chunk.content[:80].replace("\n", " ")
        vec_rank = str(r.vector_rank) if r.vector_rank else "-"
        bm25_rank = str(r.bm25_rank) if r.bm25_rank else "-"
        source = f"{r.chunk.file_path}:{r.chunk.start_line}-{r.chunk.end_line}"
        table.add_row(
            str(i),
            source,
            f"{r.rrf_score:.4f}",
            vec_rank,
            bm25_rank,
            preview,
        )

    console.print(table)

    # LLM 生成答案
    if not args.no_llm:
        console.print("\n[bold cyan]生成答案...[/bold cyan]")
        generator = AnswerGenerator(model=args.model)
        answer = generator.generate(args.question, results)
        console.print(Panel(answer, title="回答", border_style="green"))
    else:
        # 显示详细内容
        console.print("\n[bold]检索详情:[/bold]")
        for i, r in enumerate(results, 1):
            console.print(f"\n[dim]--- [{i}] {r.chunk.file_path}:{r.chunk.start_line}-{r.chunk.end_line} ---[/dim]")
            console.print(r.chunk.content[:500])
            if len(r.chunk.content) > 500:
                console.print("[dim]... (截断)[/dim]")


# ---- opc generate ----


def _run_generate(args):
    if args.generate_command == "qt":
        _run_generate_qt(args)
        return
    console.print("[yellow]请使用 opc generate qt[/yellow]")


def _run_generate_qt(args):
    project_dir = Path(args.project_dir).resolve()
    config = load_project_config(project_dir)
    try:
        registry = load_project_type_registry(project_dir, config.plugins.enabled, config.plugins.settings)
    except ValueError as exc:
        console.print(f"[red]项目类型加载失败:[/red] {exc}")
        raise SystemExit(1)

    definition = registry.get("qt")
    if definition is None:
        console.print("[yellow]Qt project type 未启用。请在 opc.toml 中设置 plugins.enabled = [\"qt\"]。[/yellow]")
        raise SystemExit(1)
    environment_diagnostics = _collect_qt_environment_diagnostics((definition,))
    _print_qt_environment_diagnostics(environment_diagnostics)
    if definition.template_provider.template_id != args.template:
        console.print(f"[red]Qt 模板不可用:[/red] {args.template}")
        raise SystemExit(1)

    target_dir = Path(args.target_dir)
    if not target_dir.is_absolute():
        target_dir = project_dir / target_dir
    try:
        variables = build_project_template_variables(args.name, class_name=args.class_name, qt_major_version="5")
        template_root = _resolve_template_root(project_dir, definition)
        file_patterns = definition.template_provider.file_patterns or None
        plan = render_template_directory(template_root, target_dir, variables, file_patterns=file_patterns, dry_run=True)
        _print_generate_file_plan(plan.planned_files, dry_run=True, base_dir=target_dir.resolve())
        if args.dry_run:
            _write_qt_generation_artifacts(
                project_dir=project_dir,
                definition=definition,
                target_dir=target_dir.resolve(),
                environment_diagnostics=environment_diagnostics,
                planned_files=plan.planned_files,
                written_files=(),
                dry_run=True,
            )
            console.print("[green]dry-run 完成，未写入文件。[/green]")
            return
        result = render_template_directory(template_root, target_dir, variables, file_patterns=file_patterns)
    except TemplateRenderError as exc:
        console.print(f"[red]Qt 项目生成失败:[/red] {exc}")
        raise SystemExit(1)

    _write_qt_generation_artifacts(
        project_dir=project_dir,
        definition=definition,
        target_dir=target_dir.resolve(),
        environment_diagnostics=environment_diagnostics,
        planned_files=plan.planned_files,
        written_files=result.written_files,
        dry_run=False,
    )
    console.print(f"[green]Qt 项目已生成:[/green] {target_dir.resolve()}")
    _print_generate_file_plan(result.written_files, dry_run=False, base_dir=target_dir.resolve())


def _write_qt_generation_artifacts(
    *,
    project_dir: Path,
    definition: ProjectTypeDefinition,
    target_dir: Path,
    environment_diagnostics: dict[str, tuple[QtEnvironmentCheckResult, ...]],
    planned_files: tuple[Path, ...],
    written_files: tuple[Path, ...],
    dry_run: bool,
) -> None:
    artifacts_dir = project_dir / "artifacts"
    has_trace = (artifacts_dir / "run_events.jsonl").exists() or (artifacts_dir / "run_trace.json").exists()
    store = RunStore.load(artifacts_dir) if has_trace else RunStore(artifacts_dir)
    previous_trace = store.read_trace()
    status = "qt_generation_dry_run" if dry_run else "qt_generation_generated"
    planned = _relative_file_paths(planned_files, target_dir)
    written = _relative_file_paths(written_files, target_dir)
    environment_payload = _environment_diagnostics_to_dict(environment_diagnostics)
    build_validation = {
        "status": "not_run",
        "reason": "opc generate qt records generation artifacts; run tests/test_qt_generation.py or CMake build validation separately.",
    }
    summary = {
        "run_id": store.run_id,
        "status": status,
        "project_type": definition.id,
        "plugin_id": definition.plugin_id,
        "template_id": definition.template_provider.template_id,
        "target_dir": str(target_dir),
        "dry_run": dry_run,
        "planned_files": planned,
        "generated_files": written,
        "environment_diagnostics": environment_payload,
        "build_validation": build_validation,
    }
    summary_path = artifacts_dir / "qt_generation.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    store.append(
        "project_type_selected",
        project_type=definition.id,
        plugin_id=definition.plugin_id,
        template_id=definition.template_provider.template_id,
        target_dir=str(target_dir),
        dry_run=dry_run,
    )
    store.append("environment_checked", project_type=definition.id, diagnostics=environment_payload)
    store.append("files_planned", project_type=definition.id, files=planned)
    if dry_run:
        store.append("qt_generation_dry_run", project_type=definition.id, summary_path=str(summary_path))
    else:
        store.append("files_generated", project_type=definition.id, files=written, summary_path=str(summary_path))
    store.append("build_validated", project_type=definition.id, **build_validation)

    _update_qt_generation_state(artifacts_dir, store.run_id, status, summary_path)
    metrics = previous_trace.get("metrics") if isinstance(previous_trace.get("metrics"), dict) else {}
    final_status = previous_trace.get("final_status") if store.trace_path.exists() else status
    store.write_trace(final_status=final_status, metrics=metrics)


def _relative_file_paths(files: tuple[Path, ...], base_dir: Path) -> list[str]:
    paths: list[str] = []
    for path in files:
        resolved = path.resolve()
        try:
            paths.append(resolved.relative_to(base_dir).as_posix())
        except ValueError:
            paths.append(str(resolved))
    return paths


def _update_qt_generation_state(artifacts_dir: Path, run_id: str, status: str, summary_path: Path) -> None:
    state_path = artifacts_dir / ".opc_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = asdict(WorkflowState(current_stage=status, completed_stages=[status], task_description="generate qt", run_id=run_id))
    artifact_paths = state.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        artifact_paths = {}
    artifact_paths["qt_generation"] = str(summary_path)
    state["artifact_paths"] = artifact_paths
    if not state.get("run_id"):
        state["run_id"] = run_id
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_template_root(project_dir: Path, definition: ProjectTypeDefinition) -> Path:
    if definition.template_provider.kind != "filesystem":
        raise TemplateRenderError(f"unsupported template provider: {definition.template_provider.kind}")
    template_path = Path(definition.template_provider.path)
    if not template_path.is_absolute():
        template_path = project_dir / template_path
    return template_path.resolve()


def _print_generate_file_plan(files: tuple[Path, ...], *, dry_run: bool, base_dir: Path | None = None) -> None:
    table = Table(title="Qt 生成文件清单")
    table.add_column("状态")
    table.add_column("文件")
    status = "planned" if dry_run else "written"
    for path in files:
        display_path = path
        if base_dir is not None:
            try:
                display_path = path.relative_to(base_dir)
            except ValueError:
                display_path = path
        table.add_row(status, str(display_path))
    console.print(table)


def _collect_qt_environment_diagnostics(
    definitions: tuple[ProjectTypeDefinition, ...],
) -> dict[str, tuple[QtEnvironmentCheckResult, ...]]:
    if not any(definition.id == "qt" for definition in definitions):
        return {}
    return {"qt": check_qt_environment()}


def _environment_diagnostics_to_dict(
    diagnostics: dict[str, tuple[QtEnvironmentCheckResult, ...]],
) -> dict[str, list[dict[str, object]]]:
    return {project_type_id: [result.as_dict() for result in results] for project_type_id, results in diagnostics.items()}


def _print_qt_environment_diagnostics(diagnostics: dict[str, tuple[QtEnvironmentCheckResult, ...]]) -> None:
    results = diagnostics.get("qt")
    if not results:
        return
    actionable = [result for result in results if result.status in {"missing", "warning"}]
    if not actionable:
        return
    console.print("[yellow]Qt 环境诊断：缺失项不会影响模板文件生成，但真实构建前需要处理。[/yellow]")
    console.print(format_qt_environment_report(actionable))


# ---- opc project-types ----


def _run_project_types(args):
    if args.project_types_command != "list":
        console.print("[yellow]请使用 opc project-types list[/yellow]")
        return

    project_dir = Path(args.project_dir).resolve()
    config = load_project_config(project_dir)
    diagnostics: list[str] = []
    definitions: tuple[ProjectTypeDefinition, ...] = ()
    try:
        registry = load_project_type_registry(project_dir, config.plugins.enabled, config.plugins.settings)
        definitions = registry.list()
    except ValueError as exc:
        diagnostics.append(str(exc))
    environment_diagnostics = _collect_qt_environment_diagnostics(definitions)

    payload = {
        "project_dir": str(project_dir),
        "enabled_plugins": list(config.plugins.enabled),
        "project_types": [_project_type_to_dict(definition) for definition in definitions],
        "diagnostics": diagnostics,
        "environment_diagnostics": _environment_diagnostics_to_dict(environment_diagnostics),
        "enablement_hint": "Enable Qt with plugins.enabled = [\"qt\"] in opc.toml; Qt checks run only after the plugin is enabled.",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if definitions:
        table = Table(title="已启用项目类型")
        table.add_column("ID", style="bold")
        table.add_column("名称")
        table.add_column("插件")
        table.add_column("模板")
        table.add_column("权限")
        table.add_column("环境检查")
        for definition in definitions:
            table.add_row(
                definition.id,
                definition.display_name,
                definition.plugin_id or definition.source,
                definition.template_provider.template_id,
                ", ".join(definition.permissions),
                "\n".join(_format_env_check(check) for check in definition.env_checks) or "-",
            )
        console.print(table)
    else:
        console.print("[yellow]当前没有已启用的项目类型。[/yellow]")

    if not config.plugins.enabled:
        console.print("[dim]Qt 插件默认禁用；在 opc.toml 中设置 plugins.enabled = [\"qt\"] 后才会加载 Qt 5.14.2/CMake 能力。[/dim]")
    _print_qt_environment_diagnostics(environment_diagnostics)
    for diagnostic in diagnostics:
        console.print(f"[red]项目类型诊断:[/red] {diagnostic}")


def _project_type_to_dict(definition: ProjectTypeDefinition) -> dict:
    return {
        "id": definition.id,
        "display_name": definition.display_name,
        "source": definition.source,
        "plugin_id": definition.plugin_id,
        "template_provider": {
            "template_id": definition.template_provider.template_id,
            "kind": definition.template_provider.kind,
            "path": definition.template_provider.path,
            "variables": list(definition.template_provider.variables),
            "file_patterns": list(definition.template_provider.file_patterns),
        },
        "permissions": list(definition.permissions),
        "env_checks": [
            {
                "id": check.id,
                "description": check.description,
                "command": check.command,
                "required": check.required,
            }
            for check in definition.env_checks
        ],
        "build_commands": [_project_command_to_dict(command) for command in definition.build_commands],
        "acceptance_checks": [_project_command_to_dict(command) for command in definition.acceptance_checks],
    }


def _project_command_to_dict(command) -> dict:
    return {
        "id": command.id,
        "command": list(command.command),
        "description": command.description,
        "required": command.required,
    }


def _format_env_check(check) -> str:
    required = "required" if check.required else "optional"
    command = f"; check: {check.command}" if check.command else ""
    return f"{check.id} ({required}): {check.description}{command}"


# ---- opc task ----

def _load_task_file(task_file: Path):
    from .task_parser import parse_tasks

    if not task_file.exists():
        console.print(f"[red]错误：任务清单不存在 {task_file}[/red]")
        return None

    return parse_tasks(task_file)


def _run_task(args):
    if args.task_command is None:
        console.print("[yellow]请使用 opc task list 或 opc task status[/yellow]")
        return

    tasks = _load_task_file(args.tasks)
    if tasks is None:
        return

    from .task_parser import tasks_to_specs
    specs = tasks_to_specs(tasks)

    if args.task_command == "list":
        table = Table(title=f"任务清单: {args.tasks}")
        table.add_column("行号", style="dim", justify="right")
        table.add_column("状态", width=8)
        table.add_column("任务")
        for task, spec in zip(tasks, specs):
            if spec.status == "completed" and not args.all:
                continue
            table.add_row(str(task.line_number + 1), "done" if spec.status == "completed" else spec.status, spec.description)
        console.print(table)
        return

    if args.task_command == "status":
        completed = sum(1 for spec in specs if spec.status == "completed")
        pending = len(specs) - completed
        console.print(Panel(
            f"[bold]任务总数[/]: {len(specs)}\n"
            f"[bold green]已完成[/]: {completed}\n"
            f"[bold yellow]待处理[/]: {pending}",
            title=f"任务状态: {args.tasks}",
        ))


# ---- opc index-list ----

def _memory_store_for_project(project_dir: Path):
    from .memory import MemoryStore

    return MemoryStore(project_dir.resolve() / "artifacts" / "memory.jsonl")


def _run_memory(args):
    from .memory import MemoryRecord, build_memory_audit_entries, delete_memory_record, evaluate_memory_write, supersede_memory_record, dedupe_memory_records

    project_dir = Path(args.project_dir)
    store = _memory_store_for_project(project_dir)
    records = store.load()

    if args.memory_command == "list":
        audit_entries = build_memory_audit_entries(records, role="engineer")

        if args.scope:
            records = [record for record in records if record.scope == args.scope]
            audit_entries = [entry for entry in audit_entries if entry.get("scope") == args.scope]
        if args.json:
            console.print(json.dumps({"records": [record.__dict__ for record in records], "audit": audit_entries}, ensure_ascii=False, indent=2))
            return
        table = Table(title="长期 Memory")
        table.add_column("ID")
        table.add_column("Scope")
        table.add_column("Source")
        table.add_column("状态")
        table.add_column("Score")
        table.add_column("内容")
        audit_map = {entry["id"]: entry for entry in audit_entries}
        for record in records:
            entry = audit_map.get(record.id, {})
            status = entry.get("status") or ("expired" if record.is_expired() else ("superseded" if record.superseded_by else "active"))
            score = entry.get("score", "-")
            table.add_row(record.id, record.scope, record.source, status, score, record.content[:80])
        console.print(table)
        return

    if args.memory_command == "add":
        record = MemoryRecord(
            content=args.content,
            scope=args.scope,
            source=args.source,
            confidence=args.confidence,
            expires_at=args.expires_at,
        )
        decision = evaluate_memory_write(record, confirmed=args.confirm)
        if decision.action == "review":
            console.print(f"[yellow]需要确认后才能写入长期 memory: {decision.reason}[/yellow]")
            return
        if decision.action != "write":
            console.print(f"[red]memory 写入被拒绝: {decision.reason}[/red]")
            return
        store.append(record)
        console.print(f"[green]memory 已写入[/green] {record.id}")
        return

    if args.memory_command == "delete":
        index = next((i for i, record in enumerate(records) if record.id == args.id), -1)
        records, decision = delete_memory_record(records, index, confirmed=args.confirm)
        if decision.action == "review":
            console.print(f"[yellow]需要确认后才能删除: {decision.reason}[/yellow]")
            return
        if decision.action != "delete":
            console.print(f"[red]memory 删除失败: {decision.reason}[/red]")
            return
        store.replace(records)
        console.print(f"[green]memory 已删除[/green] {args.id}")
        return

    if args.memory_command == "supersede":
        index = next((i for i, record in enumerate(records) if record.id == args.id), -1)
        if index < 0:
            console.print(f"[red]未找到 memory: {args.id}[/red]")
            return
        target = records[index]
        replacement = MemoryRecord(
            content=args.content,
            scope=args.scope or target.scope,
            source=args.source,
            confidence=args.confidence,
            expires_at=args.expires_at,
        )
        records, decision = supersede_memory_record(records, index, replacement, confirmed=args.confirm)
        if decision.action == "review":
            console.print(f"[yellow]需要确认后才能替代: {decision.reason}[/yellow]")
            return
        if decision.action != "supersede":
            console.print(f"[red]memory 替代失败: {decision.reason}[/red]")
            return
        store.replace(records)
        console.print(f"[green]memory 已替代[/green] {args.id} -> {replacement.id}")
        return

    if args.memory_command == "gc":
        unique_records, duplicates = dedupe_memory_records(records)
        expired = [record for record in unique_records if record.is_expired()]
        if not expired and not duplicates:
            console.print("[green]没有需要清理的过期或重复 memory[/green]")
            return
        if not args.confirm:
            table = Table(title="待清理 memory")
            table.add_column("ID")
            table.add_column("Scope")
            table.add_column("Source")
            table.add_column("状态")
            table.add_column("内容")
            for record in expired:
                table.add_row(record.id, record.scope, record.source, "expired", record.content[:80])
            for duplicate in duplicates:
                table.add_row(duplicate["duplicate_id"], duplicate.get("scope", ""), duplicate.get("source", ""), duplicate["reason"], "")
            console.print(table)
            console.print("[yellow]使用 --confirm 才会真正删除过期和重复 memory[/yellow]")
            return
        records = [record for record in unique_records if not record.is_expired()]
        store.replace(records)
        console.print(f"[green]已清理 {len(expired)} 条过期 memory，合并 {len(duplicates)} 条重复 memory[/green]")
        return

    console.print("[yellow]请使用 opc memory list/add/delete/supersede/gc[/yellow]")
    return


# ---- opc index-list ----


def _run_index_list(args):
    workspace = _get_workspace_root()
    if not workspace.exists():
        console.print("[yellow]workspace 目录不存在，暂无索引[/yellow]")
        return

    table = Table(title="已有索引")
    table.add_column("名称", style="bold")
    table.add_column("文件数")
    table.add_column("分块数")
    table.add_column("Embedding")
    table.add_column("源目录")

    from .knowledge.indexer import Indexer

    found = False
    for index_dir in sorted(workspace.iterdir()):
        index_root = index_dir / "index"
        meta = Indexer.load_meta(index_root)
        if meta:
            found = True
            table.add_row(
                meta.index_name,
                str(meta.total_files),
                str(meta.total_chunks),
                meta.embedding_model,
                "\n".join(meta.source_dirs[:3]) + ("..." if len(meta.source_dirs) > 3 else ""),
            )

    if found:
        console.print(table)
    else:
        console.print("[yellow]暂无索引。使用 opc index --name <名称> --dirs <目录> 创建索引。[/yellow]")


# ---- opc index-delete ----

def _run_index_delete(args):
    index_root = _get_index_root(args.name)
    if not index_root.exists():
        console.print(f"[yellow]索引 '{args.name}' 不存在[/yellow]")
        return

    # 确认删除
    confirm = input(f"确认删除索引 '{args.name}'? (y/n): ").strip().lower()
    if confirm != "y":
        console.print("[dim]已取消[/dim]")
        return

    # 删除向量 collection
    try:
        from .knowledge.vector_store import VectorStore
        vs = VectorStore(index_root / "vector")
        vs.delete_collection(args.name)
    except Exception:
        pass

    # 删除索引目录
    shutil.rmtree(index_root, ignore_errors=True)
    console.print(f"[green]索引 '{args.name}' 已删除[/green]")


# ---- opc runs / trace ----


def _run_runs(args):
    if args.runs_command == "cost":
        root = Path(args.project_dir) / "artifacts" if args.project_dir else Path(args.root) if args.root else _get_workspace_root()
        trend = aggregate_run_cost_trend(root, limit=args.limit)
        runs_table = Table(title="Run 成本趋势")
        runs_table.add_column("Run ID")
        runs_table.add_column("状态")
        runs_table.add_column("Input", justify="right")
        runs_table.add_column("Output", justify="right")
        runs_table.add_column("Cost", justify="right")
        runs_table.add_column("耗时(s)", justify="right")
        runs_table.add_column("Artifacts")
        for row in trend["runs"]:
            cost = "unknown" if row["estimated_cost"] is None else f"{row['estimated_cost']:.6f} {row.get('currency') or ''}".strip()
            runs_table.add_row(
                row["run_id"],
                row["status"],
                str(row["input_tokens"]),
                str(row["output_tokens"]),
                cost,
                str(row["duration_seconds"]),
                row["artifacts_dir"],
            )
        console.print(runs_table)

        stages_table = Table(title="阶段聚合")
        stages_table.add_column("Stage")
        stages_table.add_column("Runs", justify="right")
        stages_table.add_column("Input", justify="right")
        stages_table.add_column("Output", justify="right")
        stages_table.add_column("Cost", justify="right")
        stages_table.add_column("耗时(s)", justify="right")
        for row in trend["stages"]:
            stages_table.add_row(
                row["stage"],
                str(row["runs"]),
                str(row["input_tokens"]),
                str(row["output_tokens"]),
                f"{row['estimated_cost']:.6f}",
                str(row["duration_seconds"]),
            )
        console.print(stages_table)
        if trend["compatibility"]:
            console.print("[yellow]兼容性提示:[/yellow]")
            for item in trend["compatibility"]:
                console.print(f"- {item}")
        return

    if args.runs_command != "list":
        console.print("[yellow]请使用 opc runs list 或 opc runs cost[/yellow]")
        return

    root = Path(args.project_dir) / "artifacts" if args.project_dir else Path(args.root) if args.root else _get_workspace_root()
    artifacts_dirs = [root] if root.name == "artifacts" and root.exists() else find_run_artifacts(root)
    table = Table(title="Run 记录")
    table.add_column("Run ID")
    table.add_column("状态")
    table.add_column("耗时(s)", justify="right")
    table.add_column("失败原因")
    table.add_column("Artifacts")
    for artifacts_dir in artifacts_dirs:
        summary = summarize_run(artifacts_dir)
        table.add_row(
            summary.run_id,
            summary.final_status or "unknown",
            "" if summary.duration_seconds is None else str(summary.duration_seconds),
            summary.failed_reason,
            str(summary.artifacts_dir),
        )
    console.print(table)


def _run_trace(args):
    if args.trace_command == "summary":
        data = trace_summary(Path(args.artifacts_dir))
        table = Table(title="Trace 摘要")
        table.add_column("字段")
        table.add_column("值")
        for key, value in data.items():
            table.add_row(key, "" if value is None else str(value))
        console.print(table)
        return

    if args.trace_command == "show":
        from .run_store import RunStore

        store = RunStore.load(Path(args.artifacts_dir))
        events = store.read_trace().get("events", [])[-args.limit:]
        table = Table(title="Trace 事件")
        table.add_column("时间")
        table.add_column("类型")
        table.add_column("Payload")
        for event in events:
            table.add_row(event.get("timestamp", ""), event.get("type", ""), str(event.get("payload", {})))
        console.print(table)
        return

    if args.trace_command == "inspect":
        data = trace_inspect(Path(args.artifacts_dir), focus=args.focus)
        if args.json:
            console.print(json.dumps(data, ensure_ascii=False, indent=2))
            return
        table = Table(title="Trace Inspect")
        table.add_column("类别")
        table.add_column("内容")
        for key, value in data.items():
            table.add_row(key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value))
        console.print(table)
        return

    console.print("[yellow]请使用 opc trace show、opc trace summary 或 opc trace inspect[/yellow]")


# ---- opc init / doctor / config ----


def _run_config(args):
    if args.config_command != "validate":
        console.print("[yellow]请使用 opc config validate[/yellow]")
        return

    project_dir = Path(args.project_dir)
    issues = validate_project_config(project_dir, profile=args.profile)
    if issues:
        table = Table(title="配置校验失败")
        table.add_column("级别", style="red")
        table.add_column("位置")
        table.add_column("问题")
        for issue in issues:
            table.add_row(issue.level, issue.location, issue.message)
        console.print(table)
        raise SystemExit(1)

    console.print(f"[green]配置有效:[/green] {project_dir.resolve() / 'opc.toml'}")


def _run_init(args):
    project_dir = Path(args.project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir / "opc.toml"
    if target.exists() and not args.force:
        console.print(f"[yellow]opc.toml 已存在:[/yellow] {target}")
        return

    example = Path(__file__).resolve().parent.parent.parent / "opc.example.toml"
    target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]已创建 opc.toml:[/green] {target}")


def _run_doctor(args):
    project_dir = Path(args.project_dir)
    workspace_root = _get_workspace_root()
    config_path = project_dir / "opc.toml"
    api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))
    issues = validate_project_config(project_dir, profile=args.profile) if config_path.exists() else []

    table = Table(title="OPC Doctor")
    table.add_column("检查项")
    table.add_column("状态")
    table.add_column("详情")
    table.add_row("API key", "ok" if api_key_present else "missing", "ANTHROPIC_API_KEY" if api_key_present else "请在环境变量或 .env 中设置 ANTHROPIC_API_KEY")
    table.add_row("opc.toml", "ok" if config_path.exists() else "missing", str(config_path.resolve()))
    table.add_row("config validate", "ok" if not issues else "failed", "; ".join(issue.message for issue in issues) if issues else "配置可读取")
    table.add_row("workspace", "ok" if workspace_root.exists() else "missing", str(workspace_root))
    table.add_row("index root", "ok", str(_get_index_root("<name>").parent))
    table.add_row("commands", "ok", "run, resume, init, doctor, config validate, index, query, task, ui")
    console.print(table)

    if issues:
        raise SystemExit(1)


# ---- opc ui ----


def _run_ui(args):
    streamlit = shutil.which("streamlit")
    if streamlit is None:
        console.print("[red]错误：Streamlit 未安装。请先运行 pip install -e .[/red]")
        return
    ui_path = Path(__file__).resolve().parent / "ui.py"
    os.execv(streamlit, [
        streamlit,
        "run",
        str(ui_path),
        "--server.address",
        args.host,
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
    ])


if __name__ == "__main__":
    main()
