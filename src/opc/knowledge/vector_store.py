"""向量存储封装：默认优先使用 FAISS，保留 ChromaDB 作为可选后端。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Any

from .models import Chunk, RetrievalResult
from .embedder import embed_query, embed_texts, get_embedding_function


COLLECTION_PREFIX = "opc_"
DEFAULT_VECTOR_BACKEND = os.environ.get("OPC_VECTOR_BACKEND", "faiss").strip().lower()


class VectorStore:
    """向量存储门面，保持原有 add/query/delete 接口。"""

    def __init__(self, persist_dir: Path, backend: str | None = None):
        requested_backend = (backend or DEFAULT_VECTOR_BACKEND or "faiss").lower()
        self.backend_name = requested_backend
        if requested_backend == "chroma":
            self._backend = ChromaVectorStore(persist_dir)
        else:
            try:
                self._backend = FaissVectorStore(persist_dir)
                self.backend_name = "faiss"
            except ImportError:
                self._backend = ChromaVectorStore(persist_dir)
                self.backend_name = "chroma"

    def create_collection(self, index_name: str):
        self._backend.create_collection(index_name)

    def add_chunks(self, chunks: list[Chunk], batch_size: int = 200):
        self._backend.add_chunks(chunks, batch_size=batch_size)

    def query(self, query_text: str, top_k: int = 20) -> list[RetrievalResult]:
        return self._backend.query(query_text, top_k=top_k)

    def delete_chunks(self, chunk_ids: list[str]):
        self._backend.delete_chunks(chunk_ids)

    def delete_collection(self, index_name: str):
        self._backend.delete_collection(index_name)


class FaissVectorStore:
    """FAISS IndexFlatL2 持久化向量存储。"""

    def __init__(self, persist_dir: Path):
        import faiss
        import numpy as np

        self.persist_dir = persist_dir
        self.faiss = faiss
        self.np = np
        self.collection_dir: Path | None = None
        self.index = None
        self.ids: list[str] = []
        self.chunks: list[Chunk] = []

    def create_collection(self, index_name: str):
        self.collection_dir = self.persist_dir / f"{COLLECTION_PREFIX}{index_name}"
        self.collection_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def add_chunks(self, chunks: list[Chunk], batch_size: int = 200):
        self._require_collection()
        existing = set(self.ids)
        new_chunks = [chunk for chunk in chunks if chunk.chunk_id not in existing]
        for start in range(0, len(new_chunks), batch_size):
            batch = new_chunks[start:start + batch_size]
            if not batch:
                continue
            vectors = self._vectors([chunk.content for chunk in batch])
            self._ensure_index(vectors.shape[1])
            if self.index.d != vectors.shape[1]:
                raise RuntimeError(f"FAISS 维度不匹配：index={self.index.d}, vectors={vectors.shape[1]}")
            self.index.add(vectors)
            self.ids.extend(chunk.chunk_id for chunk in batch)
            self.chunks.extend(batch)
        if new_chunks:
            self._save()

    def query(self, query_text: str, top_k: int = 20) -> list[RetrievalResult]:
        if self.index is None or not self.chunks:
            return []
        query_vector = self._vector(embed_query(query_text)).reshape(1, -1)
        limit = min(top_k, len(self.chunks))
        distances, indices = self.index.search(query_vector, limit)
        results: list[RetrievalResult] = []
        for rank, (distance, index_id) in enumerate(zip(distances[0], indices[0]), 1):
            if index_id < 0 or index_id >= len(self.chunks):
                continue
            similarity = 1.0 / (1.0 + float(distance))
            results.append(RetrievalResult(chunk=self.chunks[int(index_id)], score=similarity, source="vector", rank=rank))
        return results

    def delete_chunks(self, chunk_ids: list[str]):
        if self.index is None or not chunk_ids:
            return
        removed = set(chunk_ids)
        retained = [chunk for chunk in self.chunks if chunk.chunk_id not in removed]
        if len(retained) == len(self.chunks):
            return
        self.ids = []
        self.chunks = []
        self.index = None
        self.add_chunks(retained)
        self._save()

    def delete_collection(self, index_name: str):
        collection_dir = self.persist_dir / f"{COLLECTION_PREFIX}{index_name}"
        shutil.rmtree(collection_dir, ignore_errors=True)
        if self.collection_dir == collection_dir:
            self.index = None
            self.ids = []
            self.chunks = []

    def _load(self):
        self._require_collection()
        index_path = self.collection_dir / "index.faiss"
        chunks_path = self.collection_dir / "chunks.json"
        if not index_path.exists() or not chunks_path.exists():
            return
        self.index = self.faiss.read_index(str(index_path))
        data = json.loads(chunks_path.read_text(encoding="utf-8"))
        self.ids = [item["chunk_id"] for item in data]
        self.chunks = [_chunk_from_dict(item) for item in data]

    def _save(self):
        self._require_collection()
        if self.index is not None:
            self.faiss.write_index(self.index, str(self.collection_dir / "index.faiss"))
        payload = [_chunk_to_dict(chunk) for chunk in self.chunks]
        (self.collection_dir / "chunks.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _ensure_index(self, dimension: int):
        if self.index is None:
            self.index = self.faiss.IndexFlatL2(dimension)

    def _vectors(self, texts: list[str]):
        vectors = self.np.array(embed_texts(texts), dtype="float32")
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        return vectors

    def _vector(self, values: list[float]):
        return self.np.array(values, dtype="float32")

    def _require_collection(self):
        if self.collection_dir is None:
            raise RuntimeError("Collection 未创建")


class ChromaVectorStore:
    """ChromaDB 持久化向量存储。"""

    def __init__(self, persist_dir: Path):
        import chromadb

        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.embedding_fn = get_embedding_function()
        self.collection = None

    def create_collection(self, index_name: str):
        collection_name = f"{COLLECTION_PREFIX}{index_name}"
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
        )

    def add_chunks(self, chunks: list[Chunk], batch_size: int = 200):
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

    def delete_chunks(self, chunk_ids: list[str]):
        if self.collection is None or not chunk_ids:
            return
        self.collection.delete(ids=chunk_ids)

    def delete_collection(self, index_name: str):
        collection_name = f"{COLLECTION_PREFIX}{index_name}"
        try:
            self.client.delete_collection(name=collection_name)
        except Exception:
            pass


def _chunk_to_dict(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "file_path": chunk.file_path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "content": chunk.content,
        "language": chunk.language,
        "source_name": chunk.source_name,
    }


def _chunk_from_dict(data: dict[str, Any]) -> Chunk:
    return Chunk(
        chunk_id=data["chunk_id"],
        file_path=data.get("file_path", ""),
        start_line=int(data.get("start_line", 0)),
        end_line=int(data.get("end_line", 0)),
        content=data.get("content", ""),
        language=data.get("language", ""),
        source_name=data.get("source_name", ""),
    )
