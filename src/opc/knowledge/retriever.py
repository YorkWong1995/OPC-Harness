"""多路检索 + RRF 融合"""

from __future__ import annotations

import re

from .models import Chunk, FusedResult, RetrievalResult, CODE_LANGUAGES, DOC_LANGUAGES
from .bm25_index import BM25Index
from .vector_store import VectorStore, _chunk_matches_filters
from .reranker import rerank, reranker_enabled


_CODE_QUERY_HINTS: dict[str, list[str]] = {
    "数据模型": ["models.py", "dataclass", "chunk_id", "file_path", "start_line", "end_line", "content", "language", "source_name"],
    "分块": ["chunker.py", "chunk_file", "CodeChunker", "DocChunker"],
    "索引": ["indexer.py", "BM25Index", "VectorStore", "Retriever"],
    "检索": ["retriever.py", "BM25Index", "VectorStore", "RRF"],
    "工具": ["knowledge_tools.py", "search_knowledge"],
    "配置": ["config.py", "opc.toml", "WorkflowConfig"],
    "工作流": ["workflow.py", "HarnessWorkflow", "WorkflowState"],
    "角色": ["roles.py", "Engineer", "QA", "PM", "Architect"],
    "CLI": ["cli.py", "index", "query"],
}

_CODE_QUERY_MARKERS = {
    "函数",
    "类",
    "方法",
    "字段",
    "结构",
    "数据模型",
    "实现",
    "源码",
    "代码",
    "分块",
    "配置",
    "工具",
    "入口",
    "参数",
    "返回值",
    "定义",
    "调用",
    "解析",
    "检测",
}

_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")


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

    def retrieve(self, query: str, top_k: int = 10, rrf_k: int = 60, filters: dict[str, object] | None = None) -> list[FusedResult]:
        """执行多路检索并融合结果。

        filters：可选元数据过滤，支持 language/source_name/file_path 字段，
        值可为标量（相等）或列表（属于其一）。向量后端按后端能力过滤，
        BM25 与 expand_context 结果在内存按相同条件过滤。
        """
        query_profile = self._build_query_profile(query)
        search_query = self._rewrite_query(query, query_profile)

        # 每路多取一些，保证融合后有足够结果
        fetch_k = top_k * 3

        if filters:
            vector_results = self.vector_store.query_filtered(search_query, top_k=fetch_k, filters=filters)
            bm25_results = [r for r in self.bm25_index.query(search_query, top_k=fetch_k * 2) if _chunk_matches_filters(r.chunk, filters)][:fetch_k]
        else:
            vector_results = self.vector_store.query(search_query, top_k=fetch_k)
            bm25_results = self.bm25_index.query(search_query, top_k=fetch_k)

        rrf_candidates = self.rrf_fuse(vector_results, bm25_results, top_k * 3, rrf_k)
        rrf_candidates = self._apply_query_bias(rrf_candidates, query_profile)
        if reranker_enabled():
            rrf_candidates = rerank(query, rrf_candidates, top_k)
        else:
            rrf_candidates = rrf_candidates[:top_k]
        expanded = self.expand_context(rrf_candidates, top_k=top_k)
        if filters:
            expanded = [r for r in expanded if _chunk_matches_filters(r.chunk, filters)]

        # swap summary chunks for their source chunks
        source_by_id = {c.chunk_id: c for c in self.bm25_index.chunks}
        seen: set[str] = set()
        final: list[FusedResult] = []
        for result in expanded:
            chunk = result.chunk
            if getattr(chunk, "chunk_type", "code") == "summary":
                src_id = getattr(chunk, "source_chunk_id", "")
                chunk = source_by_id.get(src_id, chunk)
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                final.append(FusedResult(
                    chunk=chunk,
                    rrf_score=result.rrf_score,
                    vector_rank=result.vector_rank,
                    bm25_rank=result.bm25_rank,
                    expansion_reason=result.expansion_reason,
                ))
        return final

    def _build_query_profile(self, query: str) -> dict[str, object]:
        identifiers = _IDENTIFIER_RE.findall(query)
        code_hints: list[str] = []
        for marker, hints in _CODE_QUERY_HINTS.items():
            if marker in query:
                code_hints.extend(hints)
        code_intent = bool(identifiers or code_hints or any(marker in query for marker in _CODE_QUERY_MARKERS))
        hints = list(dict.fromkeys([*identifiers, *code_hints]))
        return {
            "code_intent": code_intent,
            "identifiers": identifiers,
            "hints": hints,
        }

    def _rewrite_query(self, query: str, query_profile: dict[str, object]) -> str:
        if not query_profile.get("code_intent"):
            return query

        hints = query_profile.get("hints", [])
        if not isinstance(hints, list) or not hints:
            return query

        expanded = " ".join(str(hint) for hint in hints[:12])
        return f"{query}\n\n代码关键词: {expanded}"

    def _apply_query_bias(self, results: list[FusedResult], query_profile: dict[str, object]) -> list[FusedResult]:
        if not results or not query_profile.get("code_intent"):
            return results

        identifiers = [str(item) for item in query_profile.get("identifiers", [])]
        boosted: list[FusedResult] = []
        for result in results:
            bonus = self._code_priority_bonus(result.chunk, identifiers)
            boosted.append(
                FusedResult(
                    chunk=result.chunk,
                    rrf_score=result.rrf_score + bonus,
                    vector_rank=result.vector_rank,
                    bm25_rank=result.bm25_rank,
                    expansion_reason=result.expansion_reason,
                )
            )

        boosted.sort(key=lambda item: item.rrf_score, reverse=True)
        return boosted

    def _code_priority_bonus(self, chunk: Chunk, identifiers: list[str]) -> float:
        bonus = 0.0
        if chunk.language in CODE_LANGUAGES:
            bonus += 0.02
        elif chunk.language in DOC_LANGUAGES:
            bonus -= 0.004

        if chunk.file_path.startswith("src/"):
            bonus += 0.01
        elif chunk.file_path.startswith("tests/"):
            bonus += 0.004

        haystack = f"{chunk.file_path}\n{chunk.content}".lower()
        for identifier in identifiers:
            token = identifier.lower()
            if token in haystack:
                bonus += 0.01

        return min(bonus, 0.06)

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
