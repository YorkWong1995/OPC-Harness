"""测试 P2.5 BM25 索引去 pickle：JSON 持久化 + 兼容老 pickle 加载。"""

import json
import pickle

import pytest

from opc.knowledge.bm25_index import BM25Index
from opc.knowledge.models import Chunk


def _sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"f.py::L{i}-L{i + 1}",
            file_path="f.py",
            start_line=i,
            end_line=i + 1,
            content=f"def foo_{i}(): return {i}",
            language="python",
            source_name="src",
        )
        for i in range(3)
    ]


def test_save_writes_json_not_pickle(tmp_path):
    """save() 只写 chunks.json，不再写 pickle 文件。"""
    idx = BM25Index()
    idx.build(_sample_chunks())
    idx.save(tmp_path / "bm25")

    assert (tmp_path / "bm25" / "chunks.json").exists()
    assert not (tmp_path / "bm25" / "bm25.pkl").exists()
    assert not (tmp_path / "bm25" / "chunks.pkl").exists()


def test_round_trip_via_json(tmp_path):
    """save → load 后查询结果与原始索引一致。"""
    chunks = _sample_chunks()
    a = BM25Index()
    a.build(chunks)
    a.save(tmp_path / "bm25")

    b = BM25Index()
    b.load(tmp_path / "bm25")

    assert len(b.chunks) == len(chunks)
    assert b.chunks[0].chunk_id == chunks[0].chunk_id
    # 重建后能查询出非空结果
    results = b.query("foo_1")
    assert results
    assert any("foo_1" in r.chunk.content for r in results)


def test_json_payload_is_human_readable(tmp_path):
    idx = BM25Index()
    idx.build(_sample_chunks())
    idx.save(tmp_path / "bm25")

    payload = json.loads((tmp_path / "bm25" / "chunks.json").read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["chunks"]) == 3
    assert payload["chunks"][0]["language"] == "python"


def test_load_legacy_pickle_format_still_works(tmp_path):
    """老索引（仅 .pkl 文件）应仍可加载，避免破坏既有用户索引。"""
    idx_dir = tmp_path / "bm25"
    idx_dir.mkdir()

    chunks = _sample_chunks()
    legacy = BM25Index()
    legacy.build(chunks)

    # 手工写出旧 pickle 布局
    with open(idx_dir / "bm25.pkl", "wb") as f:
        pickle.dump(legacy.bm25, f)
    with open(idx_dir / "chunks.pkl", "wb") as f:
        pickle.dump(legacy.chunks, f)

    loaded = BM25Index()
    loaded.load(idx_dir)

    assert [c.chunk_id for c in loaded.chunks] == [c.chunk_id for c in chunks]


def test_load_missing_index_raises(tmp_path):
    idx = BM25Index()
    with pytest.raises(FileNotFoundError):
        idx.load(tmp_path / "nonexistent")
