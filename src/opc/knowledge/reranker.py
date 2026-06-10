"""可选的 Cross-Encoder Rerank 层。

默认关闭。设置环境变量 OPC_RERANKER_MODEL 为模型名（如 BAAI/bge-reranker-base）
或本地路径后启用。模型缓存沿用 embedder 的 OPC_MODEL_CACHE_DIR（默认 D:/opc_models）。

设计：在 RRF 融合的候选集上用 query-document 对打分，重排选出 top-k，
再交给 expand_context 扩展上下文。reranker 加载失败或未配置时返回 None，
检索流程退回原始 RRF 排序，保证不破坏现有行为。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_RERANKER: Any = None
_RERANKER_LOADED = False


def reranker_enabled() -> bool:
    return bool(os.environ.get("OPC_RERANKER_MODEL", "").strip())


def get_reranker():
    """懒加载 CrossEncoder reranker；未配置或加载失败返回 None。"""
    global _RERANKER, _RERANKER_LOADED
    if _RERANKER_LOADED:
        return _RERANKER
    _RERANKER_LOADED = True

    model_id = os.environ.get("OPC_RERANKER_MODEL", "").strip()
    if not model_id:
        _RERANKER = None
        return None

    cache_dir = Path(os.environ.get("OPC_MODEL_CACHE_DIR", "D:/opc_models"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        from sentence_transformers import CrossEncoder
        _RERANKER = CrossEncoder(model_id, cache_folder=str(cache_dir))
    except Exception as e:  # noqa: BLE001
        import sys
        sys.stderr.write(f"[Reranker 加载失败] model={model_id} error={e}\n")
        _RERANKER = None
    return _RERANKER


def rerank(query: str, results: list, top_k: int) -> list:
    """对候选结果重排，返回 top_k。

    results 为带 .chunk.content 的对象列表（FusedResult）。
    reranker 不可用时原样返回前 top_k（保持现有 RRF 排序）。
    """
    model = get_reranker()
    if model is None or not results:
        return results[:top_k]

    pairs = [(query, r.chunk.content) for r in results]
    scores = model.predict(pairs)
    ranked = sorted(zip(results, scores), key=lambda x: float(x[1]), reverse=True)
    return [r for r, _ in ranked[:top_k]]
