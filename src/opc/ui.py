"""Streamlit UI for OPC workflow, RAG query, and run history."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from opc.cli import _get_index_root, _get_workspace_root
from opc.config import ALL_OPTIONAL_ROLES
from opc.knowledge.bm25_index import BM25Index
from opc.knowledge.indexer import Indexer
from opc.knowledge.retriever import Retriever
from opc.knowledge.vector_store import VectorStore
from opc.workflow import HarnessWorkflow


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError("Streamlit 未安装，请先运行: pip install -e .") from exc

    st.set_page_config(page_title="OPC Console", layout="wide")
    st.title("OPC Console")
    page = st.sidebar.radio("功能", ["工作流执行", "RAG 查询", "历史记录"])

    if page == "工作流执行":
        render_workflow_page(st)
    elif page == "RAG 查询":
        render_rag_page(st)
    else:
        render_history_page(st)


def render_workflow_page(st) -> None:
    st.header("工作流执行")
    project_dir = Path(st.text_input("项目目录", value=str(Path.cwd()))).expanduser()
    task = st.text_area("任务描述", height=160)
    model = st.text_input("模型（可选）", value="")
    auto_confirm = st.checkbox("自动确认审批节点", value=True)
    selected_roles = st.multiselect(
        "可选角色",
        sorted(ALL_OPTIONAL_ROLES),
        default=[],
        help="Architect / Growth 可并行产出；Ops 可做运行检查；CEO 可做审查。",
    )

    if st.button("运行工作流", type="primary"):
        if not task.strip():
            st.error("请输入任务描述。")
            return
        if not project_dir.exists():
            st.error(f"项目目录不存在: {project_dir}")
            return
        with st.status("工作流运行中...", expanded=True) as status:
            workflow = HarnessWorkflow(
                task=task,
                project_dir=project_dir,
                auto_confirm=auto_confirm,
                roles=set(selected_roles),
                model=model.strip() or None,
            )
            asyncio.run(workflow.run())
            status.update(label="工作流完成", state="complete")
        render_artifacts(st, project_dir / "artifacts")


def render_rag_page(st) -> None:
    st.header("RAG 查询")
    index_name = st.text_input("索引名称", value=Path.cwd().name)
    question = st.text_area("查询问题", height=120)
    top_k = st.slider("返回结果数", min_value=1, max_value=20, value=5)

    if st.button("查询", type="primary"):
        if not index_name.strip() or not question.strip():
            st.error("请输入索引名称和查询问题。")
            return
        index_root = _get_index_root(index_name.strip())
        meta = Indexer.load_meta(index_root)
        if meta is None:
            st.error(f"索引不存在: {index_name}")
            return

        with st.spinner("检索中..."):
            bm25 = BM25Index()
            bm25.load(index_root / "bm25")
            vector_store = VectorStore(index_root / "vector")
            vector_store.create_collection(index_name.strip())
            retriever = Retriever(vector_store, bm25, meta.file_dependencies)
            results = retriever.retrieve(question, top_k=top_k)

        if not results:
            st.warning("未找到相关结果。")
            return

        rows = []
        for idx, result in enumerate(results, 1):
            chunk = result.chunk
            rows.append({
                "#": idx,
                "来源": f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}",
                "RRF": round(result.rrf_score, 4),
                "向量排名": result.vector_rank or "-",
                "BM25排名": result.bm25_rank or "-",
                "预览": chunk.content[:180].replace("\n", " "),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

        for idx, result in enumerate(results, 1):
            chunk = result.chunk
            with st.expander(f"[{idx}] {chunk.file_path}:{chunk.start_line}-{chunk.end_line}"):
                st.markdown(chunk.content)


def render_history_page(st) -> None:
    st.header("历史记录")
    root = Path(st.text_input("工作区目录", value=str(_get_workspace_root()))).expanduser()
    runs = find_runs(root)
    if not runs:
        st.info("暂无运行记录。")
        return

    labels = [str(path.parent) for path in runs]
    selected = st.selectbox("选择运行记录", labels)
    artifacts_dir = runs[labels.index(selected)]
    render_artifacts(st, artifacts_dir)


def find_runs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    candidates = [path for path in root.rglob("artifacts") if path.is_dir()]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates


def render_artifacts(st, artifacts_dir: Path) -> None:
    st.subheader("运行产物")
    if not artifacts_dir.exists():
        st.info("暂无 artifacts 目录。")
        return

    metrics_path = artifacts_dir / "run_metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        totals = metrics.get("totals", {})
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Input Tokens", totals.get("input_tokens", 0))
        col2.metric("Output Tokens", totals.get("output_tokens", 0))
        col3.metric("耗时(s)", totals.get("duration_seconds", 0))
        col4.metric("工具调用", totals.get("tool_calls", 0))

        # 质量指标
        quality = metrics.get("quality", {})
        if quality:
            qcol1, qcol2, qcol3 = st.columns(3)
            qcol1.metric("QA 通过", "是" if quality.get("qa_passed") else "否")
            qcol2.metric("返工次数", quality.get("rework_attempts", 0))
            qcol3.metric("人工介入", quality.get("human_interventions", 0))

        stages = metrics.get("stages", {})
        if stages:
            st.dataframe([
                {"阶段": name, **values}
                for name, values in stages.items()
            ], use_container_width=True, hide_index=True)

    # Run Trace 展示
    trace_path = artifacts_dir / "run_trace.json"
    if trace_path.exists():
        with st.expander("Run Trace", expanded=False):
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            st.write(f"**Run ID**: {trace.get('run_id', 'N/A')}")
            st.write(f"**最终状态**: {trace.get('final_status', 'N/A')}")
            events = trace.get("events", [])
            if events:
                # 按类型分组展示
                tool_calls = [e for e in events if e.get("type") == "tool_call"]
                stage_events = [e for e in events if e.get("type") in ("stage_started", "stage_completed")]

                if stage_events:
                    st.write(f"**阶段事件**: {len(stage_events)} 条")
                    st.dataframe([
                        {
                            "类型": e["type"],
                            "阶段": e.get("payload", {}).get("stage", ""),
                            "角色": e.get("payload", {}).get("role", ""),
                            "时间": e.get("timestamp", ""),
                        }
                        for e in stage_events
                    ], use_container_width=True, hide_index=True)

                if tool_calls:
                    st.write(f"**工具调用**: {len(tool_calls)} 次")
                    st.dataframe([
                        {
                            "工具": e.get("payload", {}).get("tool_name", ""),
                            "阶段": e.get("payload", {}).get("stage", ""),
                            "耗时(s)": e.get("payload", {}).get("elapsed", ""),
                            "错误": e.get("payload", {}).get("error", "") or "",
                        }
                        for e in tool_calls
                    ], use_container_width=True, hide_index=True)

    # 事件日志
    events_path = artifacts_dir / "run_events.jsonl"
    if events_path.exists():
        with st.expander("事件日志 (JSONL)"):
            lines = events_path.read_text(encoding="utf-8").strip().split("\n")
            st.write(f"共 {len(lines)} 条事件")
            st.code("\n".join(lines[-20:]), language="json")

    for path in sorted(artifacts_dir.glob("*.md")):
        with st.expander(path.name, expanded=path.name == "run_report.md"):
            st.markdown(path.read_text(encoding="utf-8"))

    state_path = artifacts_dir / ".opc_state.json"
    if state_path.exists():
        with st.expander("工作流状态"):
            st.json(json.loads(state_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
