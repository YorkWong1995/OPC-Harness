"""Embedding 模型封装：使用 ChromaDB 内置的 ONNXMiniLM"""

from __future__ import annotations

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2


_EMBEDDING_FN = None


def get_embedding_function():
    """获取全局 embedding 函数（懒加载单例）"""
    global _EMBEDDING_FN
    if _EMBEDDING_FN is None:
        _EMBEDDING_FN = ONNXMiniLM_L6_V2()
    return _EMBEDDING_FN


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量生成文本 embedding"""
    fn = get_embedding_function()
    return fn(texts)


def embed_query(text: str) -> list[float]:
    """生成单条查询 embedding"""
    results = embed_texts([text])
    return results[0]


EMBEDDING_MODEL_NAME = "ONNXMiniLM_L6_V2"
EMBEDDING_DIMENSION = 384
