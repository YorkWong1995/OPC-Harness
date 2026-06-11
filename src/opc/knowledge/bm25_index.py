"""BM25 索引：基于 jieba 的中文分词 + BM25Okapi"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

from .models import Chunk, RetrievalResult


def tokenize(text: str) -> list[str]:
    """混合分词：jieba 中文 + 空格英文，去停用词"""
    tokens = []
    for word in jieba.cut(text):
        w = word.strip()
        if w and len(w) > 0:
            tokens.append(w.lower())
    for word in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text):
        lowered = word.lower()
        tokens.append(lowered)
        tokens.extend(part for part in re.split(r"[_\W]+", lowered) if part)
        tokens.extend(part.lower() for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", word) if part)
    return tokens


# JSON 持久化的版本号；老 pickle 文件 (.pkl) 由 load() 兼容读入。
_INDEX_FORMAT_VERSION = 1


class BM25Index:
    """BM25 索引，支持构建、查询、持久化"""

    def __init__(self):
        self.bm25: BM25Okapi | None = None
        self.chunks: list[Chunk] = []
        self._tokenized_corpus: list[list[str]] = []

    def build(self, chunks: list[Chunk]):
        """从 chunks 构建 BM25 索引"""
        self.chunks = chunks
        self._tokenized_corpus = [tokenize(f"{c.file_path}\n{c.content}") for c in chunks]
        self.bm25 = BM25Okapi(self._tokenized_corpus)

    def query(self, query_text: str, top_k: int = 20) -> list[RetrievalResult]:
        """查询 BM25 索引，返回 top_k 结果"""
        if self.bm25 is None:
            return []
        tokenized_query = tokenize(query_text)
        scores = self.bm25.get_scores(tokenized_query)
        # 按分数排序取 top_k
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = []
        for rank, idx in enumerate(top_indices, 1):
            if abs(scores[idx]) < 1e-10:
                continue
            results.append(RetrievalResult(
                chunk=self.chunks[idx],
                score=float(scores[idx]),
                source="bm25",
                rank=rank,
            ))
        return results

    def save(self, path: Path):
        """持久化为 JSON：只存原始 chunks，加载时调 build() 重建索引。

        相比 pickle 的优势：
        - 防御纵深：不再执行任意 Python 字节码
        - 索引文件可读、跨版本可迁移
        - 重建成本低（jieba + BM25Okapi 在常规规模下毫秒级）
        """
        path.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _INDEX_FORMAT_VERSION,
            "chunks": [asdict(c) for c in self.chunks],
        }
        (path / "chunks.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def load(self, path: Path):
        """从磁盘加载索引。优先 JSON 格式；老 pickle 索引仍可加载。"""
        json_path = path / "chunks.json"
        if json_path.exists():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            chunks_data = payload.get("chunks", [])
            chunks = [Chunk(**c) for c in chunks_data]
            self.build(chunks)
            return

        # 兼容老 pickle 格式（仅在 JSON 缺失时使用）
        pkl_path = path / "bm25.pkl"
        chunks_pkl = path / "chunks.pkl"
        if pkl_path.exists() and chunks_pkl.exists():
            import pickle  # 局部导入：仅在加载老索引时引入风险面

            with open(pkl_path, "rb") as f:
                self.bm25 = pickle.load(f)
            with open(chunks_pkl, "rb") as f:
                self.chunks = pickle.load(f)
            return

        raise FileNotFoundError(f"BM25 索引不存在: {path}")
