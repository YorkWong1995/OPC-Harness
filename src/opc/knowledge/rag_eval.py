"""Lightweight local RAG evaluation helpers."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from .bm25_index import BM25Index
from .chunker import chunk_file
from .models import Chunk, EXTENSION_MAP, SKIP_DIRS
from .vector_store import VectorStore
from .retriever import Retriever


DEFAULT_PROJECT_KB_CORPUS = (
    "CLAUDE.md",
    "docs/claude",
    "docs/knowledge-retrieval-design.md",
    "docs/share/internal_technical_share.md",
    "opc.example.toml",
    "src/opc/agent.py",
    "src/opc/cli.py",
    "src/opc/config.py",
    "src/opc/rag.py",
    "src/opc/rag_bm25.py",
    "src/opc/workflow.py",
    "src/opc/tools/knowledge_tools.py",
    "src/opc/knowledge",
)


def load_rag_eval_dataset(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_eval_chunks(project_root: Path, corpus: tuple[str, ...] = DEFAULT_PROJECT_KB_CORPUS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for relative in corpus:
        path = project_root / relative
        files = [path] if path.is_file() else _iter_supported_files(path)
        for file_path in files:
            if not file_path.exists() or file_path.suffix.lower() not in EXTENSION_MAP:
                continue
            rel_path = file_path.relative_to(project_root).as_posix()
            chunks.extend(chunk_file(rel_path, file_path.read_text(encoding="utf-8", errors="replace"), source_name="opc-project-kb"))
    return chunks


def _build_retriever(chunks: list[Chunk], vector_dir: Path | None = None) -> tuple[Retriever, BM25Index, VectorStore | None]:
    """构建用于评测的 Retriever（BM25 + Vector + RRF 完整管道）。"""
    bm25 = BM25Index()
    bm25.build(chunks)

    vs: VectorStore | None = None
    if vector_dir is not None:
        vs = VectorStore(vector_dir)
        vs.create_collection("rag_eval")
        vs.add_chunks(chunks)

    retriever = Retriever(vector_store=vs, bm25_index=bm25)  # type: ignore[arg-type]
    return retriever, bm25, vs


def _eval_results(results: list, relevant_files: list[str], relevant_chunks: list[str] | None, top_k: int) -> dict[str, Any]:
    # expand_context 可能返回超过 top_k 的结果，评测只看 top_k
    results = results[:top_k]
    first_hit_rank = 0
    dcg = 0.0
    matched_count = 0
    returned = []
    for rank, result in enumerate(results, start=1):
        chunk = result.chunk
        file_path = chunk.file_path.replace("\\", "/")
        file_matched = any(file_path == exp.replace("\\", "/") for exp in relevant_files)
        chunk_matched = False
        if relevant_chunks:
            chunk_matched = any(
                (chunk.chunk_id == exp) or (f"{file_path}::L{chunk.start_line}-{chunk.end_line}" == exp.replace("\\", "/"))
                for exp in relevant_chunks
            )
        matched = file_matched or chunk_matched
        score = getattr(result, "rrf_score", getattr(result, "score", 0.0))
        returned.append({"rank": rank, "file": file_path, "chunk_id": chunk.chunk_id, "score": score, "matched": matched})
        if matched:
            matched_count += 1
            if first_hit_rank == 0:
                first_hit_rank = rank
            dcg += 1.0 / math.log2(rank + 1)

    # IDCG：理想排序下相关项全排最前，相关项数取声明数与实际命中数的较大者
    ideal_hits = min(max(len(relevant_files), matched_count), top_k)
    ideal_dcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
    ndcg = dcg / ideal_dcg if ideal_dcg else 0.0
    return {"first_hit_rank": first_hit_rank, "dcg": dcg, "ndcg": ndcg, "returned": returned}


def run_rag_eval(
    project_root: Path,
    dataset_path: Path,
    top_k: int = 3,
    vector_dir: Path | None = None,
    use_full_pipeline: bool = True,
) -> dict[str, Any]:
    """评测 RAG 管道。

    use_full_pipeline=True（默认）：使用 BM25 + Vector + RRF 完整管道（需要向量模型）。
    use_full_pipeline=False：仅 BM25 单路（快速，无需向量模型）。
    vector_dir：Vector 索引存储目录；为 None 时尝试使用内存临时目录。
    """
    import tempfile

    dataset = load_rag_eval_dataset(dataset_path)
    chunks = build_eval_chunks(project_root)

    hits = 0
    rr_sum = 0.0
    ndcg_sum = 0.0
    scored = 0          # 计入 hit_rate/MRR/nDCG 的有答案问题数
    no_answer_total = 0
    no_answer_correct = 0   # 拒答场景：top-k 未召回任何"高分相关"内容视为正确
    details = []

    def record(item, results):
        nonlocal hits, rr_sum, ndcg_sum, scored, no_answer_total, no_answer_correct
        relevant_files = item["relevant_files"]
        relevant_chunks = item.get("relevant_chunks")
        category = item.get("category", "")
        ev = _eval_results(results, relevant_files, relevant_chunks, top_k)
        fhr = ev["first_hit_rank"]
        is_no_answer = category == "no_answer" or not relevant_files
        if is_no_answer:
            no_answer_total += 1
            # 拒答正确性：没有任何结果命中预期文件（本就无预期文件，恒为未命中）
            correct = fhr == 0
            if correct:
                no_answer_correct += 1
            details.append({
                "question": item["question"],
                "category": category,
                "expected": relevant_files,
                "no_answer": True,
                "no_answer_correct": correct,
                "results": ev["returned"],
                "pipeline": pipeline_name,
            })
            return
        scored += 1
        if fhr:
            hits += 1
            rr_sum += 1.0 / fhr
        ndcg_sum += ev["ndcg"]
        details.append({
            "question": item["question"],
            "category": category,
            "expected": relevant_files,
            "hit": bool(fhr),
            "first_hit_rank": fhr or None,
            "results": ev["returned"],
            "failure_reason": "expected file not found in top-k" if not fhr else "",
            "pipeline": pipeline_name,
        })

    pipeline_name = "rrf" if use_full_pipeline else "bm25"

    if use_full_pipeline:
        import shutil as _shutil

        owns_dir = False
        if vector_dir is None:
            # 默认放 E 盘临时目录，避免占用 C 盘；evaluation 完成后清理
            base = Path(os.environ.get("OPC_EVAL_TMP_ROOT", "E:/opc_eval_tmp"))
            base.mkdir(parents=True, exist_ok=True)
            vector_dir = Path(tempfile.mkdtemp(dir=str(base)))
            owns_dir = True
        try:
            retriever, _, _ = _build_retriever(chunks, vector_dir)
            for item in dataset:
                results = retriever.retrieve(item["question"], top_k=top_k)
                record(item, results)
        finally:
            if owns_dir:
                # Windows 下向量后端可能仍持有文件句柄，清理失败不影响结果
                _shutil.rmtree(vector_dir, ignore_errors=True)
    else:
        bm25 = BM25Index()
        bm25.build(chunks)
        for item in dataset:
            results = bm25.query(item["question"], top_k=top_k)
            record(item, results)

    total = len(dataset)
    return {
        "top_k": top_k,
        "dataset": str(dataset_path),
        "pipeline": pipeline_name,
        "queries": total,
        "scored_queries": scored,
        "corpus_chunks": len(chunks),
        "hit_rate": hits / scored if scored else 0.0,
        "mrr": rr_sum / scored if scored else 0.0,
        "ndcg": ndcg_sum / scored if scored else 0.0,
        "hits": hits,
        "misses": scored - hits,
        "no_answer_total": no_answer_total,
        "no_answer_correct": no_answer_correct,
        "details": details,
    }


def _iter_supported_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    files: list[Path] = []
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        relative_parts = file_path.relative_to(path).parts
        if any(part in SKIP_DIRS for part in relative_parts):
            continue
        if file_path.suffix.lower() in EXTENSION_MAP:
            files.append(file_path)
    return sorted(files)
