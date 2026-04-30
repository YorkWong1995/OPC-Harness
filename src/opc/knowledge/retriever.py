"""多路检索 + RRF 融合"""

from __future__ import annotations

from .models import Chunk, FusedResult, RetrievalResult
from .bm25_index import BM25Index
from .vector_store import VectorStore


class Retriever:
    """多路检索器：向量 + BM25 → RRF 融合"""

    def __init__(self, vector_store: VectorStore, bm25_index: BM25Index):
        self.vector_store = vector_store
        self.bm25_index = bm25_index

    def retrieve(self, query: str, top_k: int = 10, rrf_k: int = 60) -> list[FusedResult]:
        """执行多路检索并融合结果"""
        # 每路多取一些，保证融合后有足够结果
        fetch_k = top_k * 3

        vector_results = self.vector_store.query(query, top_k=fetch_k)
        bm25_results = self.bm25_index.query(query, top_k=fetch_k)

        return self.rrf_fuse(vector_results, bm25_results, top_k, rrf_k)

    def rrf_fuse(
        self,
        vector_results: list[RetrievalResult],
        bm25_results: list[RetrievalResult],
        top_k: int,
        k: int = 60,
    ) -> list[FusedResult]:
        """Reciprocal Rank Fusion 融合算法

        公式: RRF_score(d) = Σ 1/(k + rank_i(d))
        """
        chunk_map: dict[str, FusedResult] = {}

        for r in vector_results:
            cid = r.chunk.chunk_id
            if cid not in chunk_map:
                chunk_map[cid] = FusedResult(chunk=r.chunk)
            chunk_map[cid].rrf_score += 1.0 / (k + r.rank)
            chunk_map[cid].vector_rank = r.rank

        for r in bm25_results:
            cid = r.chunk.chunk_id
            if cid not in chunk_map:
                chunk_map[cid] = FusedResult(chunk=r.chunk)
            chunk_map[cid].rrf_score += 1.0 / (k + r.rank)
            chunk_map[cid].bm25_rank = r.rank

        # 按 RRF 分数降序排列
        fused = sorted(chunk_map.values(), key=lambda x: x.rrf_score, reverse=True)
        return fused[:top_k]
