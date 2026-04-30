"""BM25 索引：基于 jieba 的中文分词 + BM25Okapi"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

from .models import Chunk, RetrievalResult


def tokenize(text: str) -> list[str]:
    """混合分词：jieba 中文 + 空格英文，去停用词"""
    tokens = []
    # jieba 处理中文段，同时保留英文词
    for word in jieba.cut(text):
        w = word.strip()
        if w and len(w) > 0:
            tokens.append(w.lower())
    return tokens


class BM25Index:
    """BM25 索引，支持构建、查询、持久化"""

    def __init__(self):
        self.bm25: BM25Okapi | None = None
        self.chunks: list[Chunk] = []
        self._tokenized_corpus: list[list[str]] = []

    def build(self, chunks: list[Chunk]):
        """从 chunks 构建 BM25 索引"""
        self.chunks = chunks
        self._tokenized_corpus = [tokenize(c.content) for c in chunks]
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
            if scores[idx] <= 0:
                continue
            results.append(RetrievalResult(
                chunk=self.chunks[idx],
                score=float(scores[idx]),
                source="bm25",
                rank=rank,
            ))
        return results

    def save(self, path: Path):
        """持久化索引到磁盘"""
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "bm25.pkl", "wb") as f:
            pickle.dump(self.bm25, f)
        with open(path / "chunks.pkl", "wb") as f:
            pickle.dump(self.chunks, f)

    def load(self, path: Path):
        """从磁盘加载索引"""
        with open(path / "bm25.pkl", "rb") as f:
            self.bm25 = pickle.load(f)
        with open(path / "chunks.pkl", "rb") as f:
            self.chunks = pickle.load(f)
