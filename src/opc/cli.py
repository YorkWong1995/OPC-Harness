"""OPC CLI 入口"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .workflow import HarnessWorkflow
from .config import load_workflow_config, normalize_roles, ALL_OPTIONAL_ROLES

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

    # ---- opc index ----
    index_parser = subparsers.add_parser("index", help="构建知识索引")
    index_parser.add_argument("--name", required=True, help="索引名称")
    index_parser.add_argument("--dirs", nargs="+", required=True, help="要索引的目录或文件")
    index_parser.add_argument("--extensions", nargs="*", help="文件扩展名过滤（如 .py .md）")
    index_parser.add_argument("--overwrite", action="store_true", help="覆盖已有索引")
    index_parser.add_argument("--verbose", action="store_true", help="详细输出")

    # ---- opc query ----
    query_parser = subparsers.add_parser("query", help="知识检索查询")
    query_parser.add_argument("question", help="查询问题")
    query_parser.add_argument("--name", required=True, help="索引名称")
    query_parser.add_argument("--top-k", type=int, default=10, help="返回结果数（默认 10）")
    query_parser.add_argument("--no-llm", action="store_true", help="不调用 LLM 生成答案，仅显示检索结果")
    query_parser.add_argument("--model", default=None, help="覆盖 LLM 模型")

    # ---- opc index-list ----
    subparsers.add_parser("index-list", help="列出所有已有索引")

    # ---- opc index-delete ----
    del_parser = subparsers.add_parser("index-delete", help="删除索引")
    del_parser.add_argument("--name", required=True, help="索引名称")

    args = parser.parse_args()

    if args.command == "run":
        _run_workflow(args)
    elif args.command == "index":
        _run_index(args)
    elif args.command == "query":
        _run_query(args)
    elif args.command == "index-list":
        _run_index_list(args)
    elif args.command == "index-delete":
        _run_index_delete(args)
    else:
        parser.print_help()


def _get_workspace_root() -> Path:
    """获取 workspace 根目录"""
    return Path(__file__).resolve().parent.parent.parent / "workspace"


def _get_index_root(name: str) -> Path:
    """获取索引根目录"""
    return _get_workspace_root() / name / "index"


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

    config = load_workflow_config(project_dir)
    roles = normalize_roles(config.roles)

    if args.ceo_review or config.ceo_review:
        roles.add("ceo")

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
    )
    workflow.run()


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

    vs = VectorStore(index_root / "chroma")
    vs.create_collection(args.name)

    retriever = Retriever(vs, bm25)

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

    # 删除 ChromaDB collection
    try:
        from .knowledge.vector_store import VectorStore
        vs = VectorStore(index_root / "chroma")
        vs.delete_collection(args.name)
    except Exception:
        pass

    # 删除索引目录
    shutil.rmtree(index_root, ignore_errors=True)
    console.print(f"[green]索引 '{args.name}' 已删除[/green]")


if __name__ == "__main__":
    main()
