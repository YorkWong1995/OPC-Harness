"""Knowledge search tool implementation for Agent."""

from __future__ import annotations


class KnowledgeToolsMixin:
    def _tool_search_knowledge(self, query: str, top_k: int = 5, index_name: str | None = None) -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"

        from ..cli import _get_index_root
        from ..knowledge.bm25_index import BM25Index
        from ..knowledge.indexer import Indexer
        from ..knowledge.retriever import Retriever
        from ..knowledge.vector_store import VectorStore

        name = index_name or self.project_dir.name
        index_root = _get_index_root(name)
        meta = Indexer.load_meta(index_root)
        if meta is None:
            return f"错误：知识索引不存在，请先运行 opc index --name {name} --dirs {self.project_dir}"

        bm25 = BM25Index()
        bm25.load(index_root / "bm25")
        vector_store = VectorStore(index_root / "vector")
        vector_store.create_collection(meta.index_name)
        retriever = Retriever(vector_store, bm25, meta.file_dependencies)
        results = retriever.retrieve(query, top_k=top_k)
        if not results:
            return "未找到相关知识。"

        lines = []
        for i, result in enumerate(results, 1):
            chunk = result.chunk
            preview = chunk.content[:800]
            if len(chunk.content) > 800:
                preview += "\n..."
            lines.append(
                f"[{i}] {chunk.file_path}:{chunk.start_line}-{chunk.end_line} "
                f"score={result.rrf_score:.4f}\n{preview}"
            )
        return "\n\n".join(lines)
