"""Lightweight local RAG evaluation helpers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .bm25_index import BM25Index
from .chunker import chunk_file
from .models import Chunk, EXTENSION_MAP, SKIP_DIRS


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


def run_rag_eval(project_root: Path, dataset_path: Path, top_k: int = 3) -> dict[str, Any]:
    dataset = load_rag_eval_dataset(dataset_path)
    chunks = build_eval_chunks(project_root)
    index = BM25Index()
    index.build(chunks)
    hits = 0
    rr_sum = 0.0
    ndcg_sum = 0.0
    details = []
    for item in dataset:
        results = index.query(item["question"], top_k=top_k)
        relevant_files = item["relevant_files"]
        first_hit_rank = 0
        dcg = 0.0
        returned = []
        for rank, result in enumerate(results, start=1):
            file_path = result.chunk.file_path.replace("\\", "/")
            matched = any(file_path == expected.replace("\\", "/") for expected in relevant_files)
            returned.append({"rank": rank, "file": file_path, "score": result.score, "matched": matched})
            if matched:
                if first_hit_rank == 0:
                    first_hit_rank = rank
                dcg += 1.0 / math.log2(rank + 1)
        if first_hit_rank:
            hits += 1
            rr_sum += 1.0 / first_hit_rank
        ideal_hits = min(len(relevant_files), top_k)
        ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
        ndcg = dcg / ideal_dcg if ideal_dcg else 0.0
        ndcg_sum += ndcg
        details.append({
            "question": item["question"],
            "expected": relevant_files,
            "hit": bool(first_hit_rank),
            "first_hit_rank": first_hit_rank or None,
            "results": returned,
            "failure_reason": "expected file not found in top-k" if not first_hit_rank else "",
        })
    total = len(dataset)
    return {
        "top_k": top_k,
        "dataset": str(dataset_path),
        "queries": total,
        "corpus_chunks": len(chunks),
        "hit_rate": hits / total if total else 0.0,
        "mrr": rr_sum / total if total else 0.0,
        "ndcg": ndcg_sum / total if total else 0.0,
        "hits": hits,
        "misses": total - hits,
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
