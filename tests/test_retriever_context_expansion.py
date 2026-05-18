"""测试检索上下文扩展。"""

from opc.knowledge.models import Chunk, FusedResult, RetrievalResult
from opc.knowledge.retriever import Retriever


class DummyVectorStore:
    def __init__(self, results):
        self.results = results

    def query(self, _query, top_k=20):
        return self.results[:top_k]


class DummyBM25Index:
    def __init__(self, chunks, results):
        self.chunks = chunks
        self.results = results

    def query(self, _query, top_k=20):
        return self.results[:top_k]


def chunk(chunk_id, file_path, start, end, content="x"):
    return Chunk(
        chunk_id=chunk_id,
        file_path=file_path,
        start_line=start,
        end_line=end,
        content=content,
        language="python",
        source_name="project",
    )


def test_retrieve_expands_neighbor_chunks():
    first = chunk("app::1", "app.py", 1, 10)
    second = chunk("app::2", "app.py", 11, 20)
    bm25_result = RetrievalResult(chunk=first, score=1.0, source="bm25", rank=1)
    retriever = Retriever(DummyVectorStore([]), DummyBM25Index([first, second], [bm25_result]))

    results = retriever.retrieve("app", top_k=2)

    assert [result.chunk.chunk_id for result in results] == ["app::1", "app::2"]
    assert results[1].expansion_reason == "neighbor"


def test_retrieve_expands_related_file_chunks():
    app = chunk("app::1", "app.py", 1, 10)
    config = chunk("config::1", "config.py", 1, 10)
    bm25_result = RetrievalResult(chunk=app, score=1.0, source="bm25", rank=1)
    retriever = Retriever(
        DummyVectorStore([]),
        DummyBM25Index([app, config], [bm25_result]),
        {"app.py": {"dependencies": ["config.py"], "dependents": []}},
    )

    results = retriever.retrieve("app", top_k=2)

    assert [result.chunk.chunk_id for result in results] == ["app::1", "config::1"]
    assert results[1].expansion_reason == "related:config.py"


def test_rrf_fuse_preserves_original_ranks():
    app = chunk("app::1", "app.py", 1, 10)
    retriever = Retriever(DummyVectorStore([]), DummyBM25Index([app], []))

    results = retriever.rrf_fuse([], [RetrievalResult(chunk=app, score=1.0, source="bm25", rank=3)], top_k=1)

    assert results == [FusedResult(chunk=app, rrf_score=1.0 / 63, bm25_rank=3)]
