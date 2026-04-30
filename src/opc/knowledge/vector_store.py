"""ChromaDB 向量存储封装"""

from __future__ import annotations

from pathlib import Path

import chromadb

from .models import Chunk, RetrievalResult
from .embedder import get_embedding_function, EMBEDDING_MODEL_NAME


COLLECTION_PREFIX = "opc_"


class VectorStore:
    """ChromaDB 持久化向量存储"""

    def __init__(self, persist_dir: Path):
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.embedding_fn = get_embedding_function()
        self.collection = None

    def create_collection(self, index_name: str):
        """创建或获取 collection"""
        collection_name = f"{COLLECTION_PREFIX}{index_name}"
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
        )

    def add_chunks(self, chunks: list[Chunk], batch_size: int = 200):
        """批量添加 chunks 到向量库"""
        if self.collection is None:
            raise RuntimeError("Collection 未创建")

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            ids = [c.chunk_id for c in batch]
            documents = [c.content for c in batch]
            metadatas = [{
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "language": c.language,
                "source_name": c.source_name,
            } for c in batch]

            # 跳过已存在的 id
            existing = set(self.collection.get(ids=ids)["ids"]) if self.collection.count() > 0 else set()
            new_ids, new_docs, new_metas = [], [], []
            for id_, doc, meta in zip(ids, documents, metadatas):
                if id_ not in existing:
                    new_ids.append(id_)
                    new_docs.append(doc)
                    new_metas.append(meta)

            if new_ids:
                self.collection.add(
                    ids=new_ids,
                    documents=new_docs,
                    metadatas=new_metas,
                )

    def query(self, query_text: str, top_k: int = 20) -> list[RetrievalResult]:
        """向量查询"""
        if self.collection is None:
            return []

        results = self.collection.query(
            query_texts=[query_text],
            n_results=min(top_k, self.collection.count()) if self.collection.count() > 0 else top_k,
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        retrieval_results = []
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        documents = results["documents"][0]

        for rank, (id_, dist, meta, doc) in enumerate(zip(ids, distances, metadatas, documents), 1):
            # ChromaDB 返回的是 L2 距离，转换为相似度
            similarity = 1.0 / (1.0 + dist)
            chunk = Chunk(
                chunk_id=id_,
                file_path=meta.get("file_path", ""),
                start_line=meta.get("start_line", 0),
                end_line=meta.get("end_line", 0),
                content=doc,
                language=meta.get("language", ""),
                source_name=meta.get("source_name", ""),
            )
            retrieval_results.append(RetrievalResult(
                chunk=chunk,
                score=float(similarity),
                source="vector",
                rank=rank,
            ))

        return retrieval_results

    def delete_collection(self, index_name: str):
        """删除 collection"""
        collection_name = f"{COLLECTION_PREFIX}{index_name}"
        try:
            self.client.delete_collection(name=collection_name)
        except Exception:
            pass
