"""Knowledge search tool implementation for Agent."""

from __future__ import annotations


class KnowledgeToolsMixin:
    def _tool_search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        index_name: str | None = None,
        language: str | None = None,
        source_name: str | None = None,
    ) -> str:
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

        filters: dict[str, object] = {}
        if language:
            filters["language"] = language
        if source_name:
            filters["source_name"] = source_name
        results = retriever.retrieve(query, top_k=top_k, filters=filters or None)
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

    def _tool_search_symbol(
        self,
        name: str,
        kind: str | None = None,
        index_name: str | None = None,
        limit: int = 20,
    ) -> str:
        """搜索 C/C++ 符号定义（函数/类/宏/枚举等），基于 ctags"""
        if not self.project_dir:
            return "错误：未设置项目目录"

        from ..cli import _get_index_root
        from ..knowledge.cpp_symbol_search import CppSymbolSearch
        from ..knowledge.indexer import Indexer

        idx_name = index_name or self.project_dir.name
        index_root = _get_index_root(idx_name)
        meta = Indexer.load_meta(index_root)
        if meta is None:
            return f"错误：知识索引不存在，请先运行 opc index --name {idx_name}"

        # 扫描源目录构建符号索引
        symbol_index = CppSymbolSearch()
        from pathlib import Path
        for source_dir_str in meta.source_dirs:
            source_dir = Path(source_dir_str)
            if source_dir.exists():
                symbol_index.index_directory(source_dir)

        if not symbol_index.symbols:
            return "未找到任何符号。请确认 ctags 已安装并在 PATH 中（universal-ctags 推荐）。"

        # 执行搜索
        results = symbol_index.search(name, kind=kind, limit=limit)
        if not results:
            return f"未找到符号 '{name}'"

        lines = []
        for i, symbol in enumerate(results, 1):
            lines.append(
                f"[{i}] {symbol.signature}\n"
                f"    位置: {symbol.file_path}:{symbol.line}"
                + (f"\n    所属: {symbol.owner}" if symbol.owner else "")
            )
        return "\n\n".join(lines)

