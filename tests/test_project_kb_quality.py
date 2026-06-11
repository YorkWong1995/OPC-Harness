"""Curated OPC project knowledge-base retrieval quality tests."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from opc.knowledge.bm25_index import BM25Index
from opc.knowledge.chunker import chunk_file
from opc.knowledge.models import Chunk, EXTENSION_MAP, SKIP_DIRS
from opc.knowledge.rag_eval import run_rag_eval


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "rag_eval_dataset.json"

PROJECT_KB_CORPUS = [
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
]


def _load_dataset() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _iter_corpus_files() -> list[Path]:
    files: list[Path] = []
    for relative in PROJECT_KB_CORPUS:
        path = PROJECT_ROOT / relative
        if path.is_file():
            files.append(path)
            continue
        for file_path in path.rglob("*"):
            if not file_path.is_file():
                continue
            relative_parts = file_path.relative_to(path).parts
            if any(part in SKIP_DIRS for part in relative_parts):
                continue
            if file_path.suffix.lower() in EXTENSION_MAP:
                files.append(file_path)
    return sorted(set(files))


def _build_project_kb_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for file_path in _iter_corpus_files():
        rel_path = file_path.relative_to(PROJECT_ROOT).as_posix()
        content = file_path.read_text(encoding="utf-8", errors="replace")
        chunks.extend(chunk_file(rel_path, content, source_name="opc-project-kb"))
    return chunks


def _matches_expected(file_path: str, relevant_files: list[str]) -> bool:
    normalized = file_path.replace("\\", "/")
    return any(normalized == expected.replace("\\", "/") for expected in relevant_files)


def _metrics(index: BM25Index, dataset: list[dict], top_k: int) -> dict[str, float | int | list[str]]:
    hits = 0
    rr_sum = 0.0
    ndcg_sum = 0.0
    misses: list[str] = []

    for item in dataset:
        results = index.query(item["question"], top_k=top_k)
        relevant_files = item["relevant_files"]
        first_hit_rank = 0
        dcg = 0.0
        for rank, result in enumerate(results, start=1):
            if _matches_expected(result.chunk.file_path, relevant_files):
                if first_hit_rank == 0:
                    first_hit_rank = rank
                dcg += 1.0 / math.log2(rank + 1)

        if first_hit_rank:
            hits += 1
            rr_sum += 1.0 / first_hit_rank
        else:
            misses.append(item["question"])

        ideal_hits = min(len(relevant_files), top_k)
        ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
        ndcg_sum += dcg / ideal_dcg if ideal_dcg else 0.0

    total = len(dataset)
    return {
        "hit_rate": hits / total,
        "mrr": rr_sum / total,
        "ndcg": ndcg_sum / total,
        "hits": hits,
        "total": total,
        "misses": misses,
    }


@pytest.fixture(scope="module")
def project_kb_chunks() -> list[Chunk]:
    return _build_project_kb_chunks()


@pytest.fixture(scope="module")
def project_kb_bm25(project_kb_chunks: list[Chunk]) -> BM25Index:
    index = BM25Index()
    index.build(project_kb_chunks)
    return index


@pytest.fixture(scope="module")
def eval_dataset() -> list[dict]:
    return _load_dataset()


def test_curated_project_kb_corpus_excludes_noisy_run_records(project_kb_chunks: list[Chunk]):
    files = {chunk.file_path for chunk in project_kb_chunks}

    assert "CLAUDE.md" in files
    assert "docs/claude/roles.md" in files
    assert "docs/share/internal_technical_share.md" in files
    assert "docs/runs/tasks.md" not in files
    assert not any(path.startswith("docs/completed_tasks/") for path in files)


def test_curated_project_kb_has_eval_sources(project_kb_chunks: list[Chunk], eval_dataset: list[dict]):
    indexed_files = {chunk.file_path for chunk in project_kb_chunks}
    missing = sorted({
        expected
        for item in eval_dataset
        for expected in item["relevant_files"]
        if expected not in indexed_files
    })

    assert not missing, "评估集引用的文件未进入精选知识库语料: " + ", ".join(missing)


def test_curated_project_kb_bm25_baseline_quality(project_kb_bm25: BM25Index, eval_dataset: list[dict]):
    metrics = _metrics(project_kb_bm25, eval_dataset, top_k=3)

    assert metrics["hit_rate"] >= 0.5, (
        f"BM25 baseline top-3 命中率 {metrics['hit_rate']:.2%} "
        f"({metrics['hits']}/{metrics['total']}) 低于 50%；misses={metrics['misses'][:5]}"
    )
    assert metrics["mrr"] >= 0.35, f"BM25 baseline MRR {metrics['mrr']:.3f} 低于 0.35"
    assert metrics["ndcg"] >= 0.35, f"BM25 baseline NDCG@3 {metrics['ndcg']:.3f} 低于 0.35"


def test_curated_project_kb_top3_target_diagnostic(project_kb_bm25: BM25Index, eval_dataset: list[dict]):
    metrics = _metrics(project_kb_bm25, eval_dataset, top_k=3)

    assert metrics["hit_rate"] < 0.8, "BM25 baseline 已达到 80% top-3 目标，请收紧该诊断测试。"
    assert any("Chunk 数据模型" in miss or "索引构建" in miss for miss in metrics["misses"]), (
        "当前未达标原因应主要来自中文自然语言查询英文代码结构的召回短板。"
    )


@pytest.mark.parametrize("item", _load_dataset(), ids=lambda item: item["question"])
def test_each_project_kb_query_returns_ranked_results(project_kb_bm25: BM25Index, item: dict):
    results = project_kb_bm25.query(item["question"], top_k=5)

    assert results, f"查询无结果: {item['question']}"
    assert all(result.score > 0 for result in results)


def test_lightweight_rag_eval_reports_hits_and_misses():
    report = run_rag_eval(PROJECT_ROOT, FIXTURE_PATH, top_k=3, use_full_pipeline=False)

    assert report["queries"] == len(_load_dataset())
    assert report["hit_rate"] >= 0.4
    assert report["details"]
    assert {"question", "expected", "hit", "results", "failure_reason"}.issubset(report["details"][0])
