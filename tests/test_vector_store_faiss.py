"""测试 FAISS 向量后端的持久化与查询接口。"""

from __future__ import annotations

import pickle
import sys
from types import SimpleNamespace

from opc.knowledge.models import Chunk


class FakeIndexFlatL2:
    def __init__(self, dimension):
        self.d = dimension
        self.vectors = []

    def add(self, vectors):
        self.vectors.extend([list(vector) for vector in vectors])

    def search(self, queries, limit):
        query = list(queries[0])
        scored = []
        for index, vector in enumerate(self.vectors):
            distance = sum((left - right) ** 2 for left, right in zip(query, vector))
            scored.append((distance, index))
        scored.sort(key=lambda item: item[0])
        selected = scored[:limit]
        return [[distance for distance, _ in selected]], [[index for _, index in selected]]


def install_fake_faiss(monkeypatch):
    def write_index(index, path):
        with open(path, "wb") as file:
            pickle.dump(index, file)

    def read_index(path):
        with open(path, "rb") as file:
            return pickle.load(file)

    fake_faiss = SimpleNamespace(IndexFlatL2=FakeIndexFlatL2, write_index=write_index, read_index=read_index)
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)


def test_faiss_backend_add_query_and_reload(tmp_path, monkeypatch):
    install_fake_faiss(monkeypatch)
    monkeypatch.setattr("opc.knowledge.vector_store.embed_texts", lambda texts: [[float(len(text)), 0.0] for text in texts])
    monkeypatch.setattr("opc.knowledge.vector_store.embed_query", lambda text: [float(len(text)), 0.0])

    from opc.knowledge.vector_store import VectorStore

    chunks = [
        Chunk("a", "a.py", 1, 1, "aa", "python", "src"),
        Chunk("b", "b.py", 1, 1, "bbbb", "python", "src"),
    ]
    store = VectorStore(tmp_path, backend="faiss")
    store.create_collection("demo")
    store.add_chunks(chunks)

    results = store.query("xxx", top_k=2)

    assert store.backend_name == "faiss"
    assert [result.chunk.chunk_id for result in results] == ["a", "b"]
    assert (tmp_path / "opc_demo" / "index.faiss").exists()
    assert (tmp_path / "opc_demo" / "chunks.json").exists()

    reloaded = VectorStore(tmp_path, backend="faiss")
    reloaded.create_collection("demo")
    assert [result.chunk.chunk_id for result in reloaded.query("xxx", top_k=1)] == ["a"]


def test_faiss_backend_delete_rebuilds_index(tmp_path, monkeypatch):
    install_fake_faiss(monkeypatch)
    monkeypatch.setattr("opc.knowledge.vector_store.embed_texts", lambda texts: [[float(len(text)), 0.0] for text in texts])
    monkeypatch.setattr("opc.knowledge.vector_store.embed_query", lambda text: [float(len(text)), 0.0])

    from opc.knowledge.vector_store import VectorStore

    store = VectorStore(tmp_path, backend="faiss")
    store.create_collection("demo")
    store.add_chunks([
        Chunk("a", "a.py", 1, 1, "aa", "python", "src"),
        Chunk("b", "b.py", 1, 1, "bbbb", "python", "src"),
    ])

    store.delete_chunks(["a"])

    assert [result.chunk.chunk_id for result in store.query("xx", top_k=2)] == ["b"]


def test_vector_store_falls_back_to_chroma_when_faiss_missing(tmp_path, monkeypatch):
    from opc.knowledge import vector_store

    def fail_faiss(_self, _persist_dir):
        raise ImportError("faiss missing")

    def init_chroma(self, _persist_dir):
        self.collection = None

    monkeypatch.setattr(vector_store.FaissVectorStore, "__init__", fail_faiss)
    monkeypatch.setattr(vector_store.ChromaVectorStore, "__init__", init_chroma)

    store = vector_store.VectorStore(tmp_path, backend="faiss")

    assert store.backend_name == "chroma"
