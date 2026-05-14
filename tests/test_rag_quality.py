"""测试 RAG 检索质量：top-k 命中率和 MRR 指标

基于 tests/fixtures/rag_eval_dataset.json 评估集，
对 SimpleRAG 和 BM25RAG 计算检索质量指标。

阈值：top-3 命中率 > 60%
"""

import json
import math
import os
from pathlib import Path

import pytest

from opc.rag import SimpleRAG
from opc.rag_bm25 import BM25RAG, BM25_AVAILABLE

pytestmark = pytest.mark.skipif(
    os.environ.get("OPC_RUN_RAG_QUALITY") != "1",
    reason="RAG quality tests build project-level indexes; set OPC_RUN_RAG_QUALITY=1 to run.",
)

# ── 路径常量 ──────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "rag_eval_dataset.json"


# ── 辅助函数 ──────────────────────────────────────────────


def load_eval_dataset() -> list[dict]:
    """加载评估数据集"""
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _file_hit(results: list[dict], relevant_files: list[str]) -> bool:
    """判断检索结果中是否命中了任一期望文件（路径后缀匹配）"""
    for result in results:
        result_file = result["file"].replace("\\", "/")
        for expected in relevant_files:
            expected_norm = expected.replace("\\", "/")
            if result_file.endswith(expected_norm) or expected_norm.endswith(result_file):
                return True
    return False


def _reciprocal_rank(results: list[dict], relevant_files: list[str]) -> float:
    """计算单个查询的 Reciprocal Rank"""
    for i, result in enumerate(results):
        result_file = result["file"].replace("\\", "/")
        for expected in relevant_files:
            expected_norm = expected.replace("\\", "/")
            if result_file.endswith(expected_norm) or expected_norm.endswith(result_file):
                return 1.0 / (i + 1)
    return 0.0


def _ndcg_at_k(results: list[dict], relevant_files: list[str], k: int) -> float:
    """计算二元相关性的 NDCG@k"""
    dcg = 0.0
    for i, result in enumerate(results[:k], start=1):
        result_file = result["file"].replace("\\", "/")
        relevant = any(
            result_file.endswith(expected.replace("\\", "/"))
            or expected.replace("\\", "/").endswith(result_file)
            for expected in relevant_files
        )
        if relevant:
            dcg += 1.0 / math.log2(i + 1)

    ideal_hits = min(len(relevant_files), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def compute_metrics(
    rag: SimpleRAG, dataset: list[dict], top_k: int = 3
) -> dict:
    """计算 top-k 命中率和 MRR"""
    hits = 0
    rr_sum = 0.0
    ndcg_sum = 0.0
    total = len(dataset)

    for item in dataset:
        question = item["question"]
        relevant_files = item["relevant_files"]

        results = rag.search(question, top_k=top_k)

        if _file_hit(results, relevant_files):
            hits += 1

        rr_sum += _reciprocal_rank(results, relevant_files)
        ndcg_sum += _ndcg_at_k(results, relevant_files, top_k)

    hit_rate = hits / total if total > 0 else 0.0
    mrr = rr_sum / total if total > 0 else 0.0
    ndcg = ndcg_sum / total if total > 0 else 0.0

    return {"hit_rate": hit_rate, "mrr": mrr, "ndcg": ndcg, "hits": hits, "total": total}


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def eval_dataset() -> list[dict]:
    return load_eval_dataset()


@pytest.fixture(scope="module")
def simple_rag() -> SimpleRAG:
    """以项目根目录为文档目录构建 SimpleRAG 索引"""
    return SimpleRAG(PROJECT_ROOT)


@pytest.fixture(scope="module")
def bm25_rag() -> BM25RAG | None:
    """以项目根目录为文档目录构建 BM25RAG 索引"""
    if not BM25_AVAILABLE:
        return None
    return BM25RAG(PROJECT_ROOT)


# ── SimpleRAG 测试 ────────────────────────────────────────


class TestSimpleRAGQuality:
    """SimpleRAG 检索质量测试"""

    def test_index_not_empty(self, simple_rag: SimpleRAG):
        """索引应包含文档块"""
        assert len(simple_rag.chunks) > 0

    def test_top3_hit_rate(self, simple_rag: SimpleRAG, eval_dataset: list[dict]):
        """top-3 命中率应 > 60%"""
        metrics = compute_metrics(simple_rag, eval_dataset, top_k=3)
        assert metrics["hit_rate"] > 0.6, (
            f"SimpleRAG top-3 命中率 {metrics['hit_rate']:.2%} "
            f"({metrics['hits']}/{metrics['total']}) 未达到 60% 阈值"
        )

    def test_mrr(self, simple_rag: SimpleRAG, eval_dataset: list[dict]):
        """MRR 应为正值（基本可用性检查）"""
        metrics = compute_metrics(simple_rag, eval_dataset, top_k=3)
        assert metrics["mrr"] > 0.0, "SimpleRAG MRR 为 0，检索完全无效"

    def test_ndcg(self, simple_rag: SimpleRAG, eval_dataset: list[dict]):
        """NDCG 应为正值（排序质量检查）"""
        metrics = compute_metrics(simple_rag, eval_dataset, top_k=3)
        assert metrics["ndcg"] > 0.0, "SimpleRAG NDCG 为 0，排序完全无效"


# ── BM25RAG 测试 ─────────────────────────────────────────


@pytest.mark.skipif(not BM25_AVAILABLE, reason="rank-bm25 或 jieba 未安装")
class TestBM25RAGQuality:
    """BM25RAG 检索质量测试"""

    def test_index_not_empty(self, bm25_rag: BM25RAG):
        """索引应包含文档块"""
        assert len(bm25_rag.chunks) > 0

    def test_top3_hit_rate(self, bm25_rag: BM25RAG, eval_dataset: list[dict]):
        """top-3 命中率应 > 60%"""
        metrics = compute_metrics(bm25_rag, eval_dataset, top_k=3)
        assert metrics["hit_rate"] > 0.6, (
            f"BM25RAG top-3 命中率 {metrics['hit_rate']:.2%} "
            f"({metrics['hits']}/{metrics['total']}) 未达到 60% 阈值"
        )

    def test_mrr(self, bm25_rag: BM25RAG, eval_dataset: list[dict]):
        """MRR 应为正值"""
        metrics = compute_metrics(bm25_rag, eval_dataset, top_k=3)
        assert metrics["mrr"] > 0.0, "BM25RAG MRR 为 0，检索完全无效"

    def test_ndcg(self, bm25_rag: BM25RAG, eval_dataset: list[dict]):
        """NDCG 应为正值"""
        metrics = compute_metrics(bm25_rag, eval_dataset, top_k=3)
        assert metrics["ndcg"] > 0.0, "BM25RAG NDCG 为 0，排序完全无效"

    def test_bm25_beats_simple(
        self, simple_rag: SimpleRAG, bm25_rag: BM25RAG, eval_dataset: list[dict]
    ):
        """BM25 的 MRR 应不低于 SimpleRAG（回归保护）"""
        simple_metrics = compute_metrics(simple_rag, eval_dataset, top_k=3)
        bm25_metrics = compute_metrics(bm25_rag, eval_dataset, top_k=3)
        assert bm25_metrics["mrr"] >= simple_metrics["mrr"] * 0.9, (
            f"BM25 MRR ({bm25_metrics['mrr']:.3f}) 显著低于 "
            f"SimpleRAG ({simple_metrics['mrr']:.3f})"
        )


# ── 参数化单条查询诊断 ────────────────────────────────────


@pytest.fixture(scope="module")
def eval_questions(eval_dataset: list[dict]) -> list[str]:
    return [item["question"] for item in eval_dataset]


def test_each_query_returns_results(simple_rag: SimpleRAG, eval_dataset: list[dict]):
    """每条查询至少应返回 1 个结果（检索不应完全失败）"""
    empty_queries = []
    for item in eval_dataset:
        results = simple_rag.search(item["question"], top_k=3)
        if not results:
            empty_queries.append(item["question"])

    # 允许最多 20% 的查询无结果
    max_empty = len(eval_dataset) * 0.2
    assert len(empty_queries) <= max_empty, (
        f"{len(empty_queries)} 条查询无结果（超过 20% 阈值）：\n"
        + "\n".join(f"  - {q}" for q in empty_queries[:5])
    )
