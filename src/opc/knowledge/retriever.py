"""多路检索 + RRF 融合"""

from __future__ import annotations

from .models import Chunk, FusedResult, RetrievalResult
from .bm25_index import BM25Index
from .vector_store import VectorStore


class Retriever:
    """多路检索器：向量 + BM25 → RRF 融合"""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        file_dependencies: dict[str, dict[str, list[str]]] | None = None,
    ):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.file_dependencies = file_dependencies or {}

    def retrieve(self, query: str, top_k: int = 10, rrf_k: int = 60) -> list[FusedResult]:
        """执行多路检索并融合结果"""
        # 每路多取一些，保证融合后有足够结果
        fetch_k = top_k * 3

        vector_results = self.vector_store.query(query, top_k=fetch_k)
        bm25_results = self.bm25_index.query(query, top_k=fetch_k)

        fused = self.rrf_fuse(vector_results, bm25_results, top_k, rrf_k)
        return self.expand_context(fused, top_k=top_k)

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

    def expand_context(self, results: list[FusedResult], top_k: int | None = None) -> list[FusedResult]:
        """为召回 chunk 补充相邻 chunk 和文件依赖上下文。"""
        if not results:
            return []
        expanded: list[FusedResult] = []
        seen: set[str] = set()
        chunks_by_file: dict[str, list[Chunk]] = {}
        for chunk in self.bm25_index.chunks:
            chunks_by_file.setdefault(chunk.file_path, []).append(chunk)
        for chunks in chunks_by_file.values():
            chunks.sort(key=lambda chunk: (chunk.start_line, chunk.end_line, chunk.chunk_id))

        def add(chunk: Chunk, score: float, reason: str = "") -> None:
            if chunk.chunk_id in seen:
                return
            seen.add(chunk.chunk_id)
            expanded.append(FusedResult(chunk=chunk, rrf_score=score, expansion_reason=reason))

        for result in results:
            chunk = result.chunk
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                expanded.append(result)
            for neighbor in self._neighbor_chunks(chunk, chunks_by_file):
                add(neighbor, result.rrf_score * 0.5, "neighbor")
            for related_file in self._related_files(chunk.file_path):
                related_chunk = self._first_chunk(related_file, chunks_by_file)
                if related_chunk is not None:
                    add(related_chunk, result.rrf_score * 0.4, f"related:{related_file}")

        limit = top_k or len(expanded)
        return expanded[: max(limit, len(results))]

    def _neighbor_chunks(self, chunk: Chunk, chunks_by_file: dict[str, list[Chunk]]) -> list[Chunk]:
        chunks = chunks_by_file.get(chunk.file_path, [])
        try:
            idx = next(i for i, candidate in enumerate(chunks) if candidate.chunk_id == chunk.chunk_id)
        except StopIteration:
            return []
        neighbors = []
        if idx > 0:
            neighbors.append(chunks[idx - 1])
        if idx + 1 < len(chunks):
            neighbors.append(chunks[idx + 1])
        return neighbors

    def _related_files(self, file_path: str) -> list[str]:
        relation = self.file_dependencies.get(file_path, {})
        files = relation.get("dependencies", []) + relation.get("dependents", [])
        return list(dict.fromkeys(files))

    @staticmethod
    def _first_chunk(file_path: str, chunks_by_file: dict[str, list[Chunk]]) -> Chunk | None:
        chunks = chunks_by_file.get(file_path, [])
        return chunks[0] if chunks else None
