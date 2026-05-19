"""Embedding 模型封装

支持两种模型：
1. ONNXMiniLM_L6_V2 (默认，轻量英文模型) — ChromaDB 内置
2. BAAI/bge-small-zh-v1.5（中文检索更稳）— 需 sentence-transformers

通过环境变量控制：
- OPC_EMBEDDING_MODEL:  "minilm" (默认) | "bge-small-zh" | "bge-m3" | 本地路径 | HuggingFace 模型名
- OPC_MODEL_CACHE_DIR:  模型缓存目录（默认 D:/opc_models）

C 盘空间受限场景：设置 OPC_MODEL_CACHE_DIR=D:/opc_models 把模型缓存到 D 盘。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# 默认缓存路径放在 D 盘，避免占用 C 盘
DEFAULT_CACHE_DIR = Path(os.environ.get("OPC_MODEL_CACHE_DIR", "D:/opc_models"))

# 默认模型优先保证基础安装可运行；中文增强模型通过 OPC_EMBEDDING_MODEL 显式启用。
_DEFAULT_MODEL = os.environ.get("OPC_EMBEDDING_MODEL", "minilm").strip()

# bge 系列在 HuggingFace 上的仓库名
BGE_M3_REPO = "BAAI/bge-m3"
BGE_SMALL_ZH_REPO = "BAAI/bge-small-zh-v1.5"

# 模型别名
_MODEL_ALIASES = {
    "minilm": "ONNXMiniLM_L6_V2",
    "bge-m3": BGE_M3_REPO,
    "bge-small-zh": BGE_SMALL_ZH_REPO,
}

_MODEL_DIMENSIONS = {
    "ONNXMiniLM_L6_V2": 384,
    BGE_SMALL_ZH_REPO: 512,
    BGE_M3_REPO: 1024,
}


def _resolve_model_id(name: str) -> str:
    """把别名转换成实际的模型标识"""
    return _MODEL_ALIASES.get(name.lower(), name)


_EMBEDDING_FN: Any = None
_CURRENT_MODEL_ID: str | None = None
_CURRENT_DIMENSION: int | None = None


def _ensure_cache_dir() -> Path:
    """确保缓存目录存在，配置相关环境变量"""
    cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 指引 HuggingFace / transformers / sentence-transformers 使用该目录
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_dir / "transformers"))
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(cache_dir / "sentence-transformers"))
    return cache_dir


def _print_manual_download_hint(model_id: str, cache_dir: Path, error: Exception) -> None:
    """下载失败时打印手动下载指引"""
    local_dir_name = model_id.replace("/", "_")
    hint = f"""
[Embedding 模型加载失败]
模型: {model_id}
缓存目录: {cache_dir}
错误: {error}

请按以下步骤手动下载模型到 D 盘:

方式 1: 使用 git lfs (需要先安装 git-lfs)
  git lfs install
  cd /d D:\\
  mkdir opc_models 2>NUL
  cd opc_models
  git clone https://huggingface.co/{model_id}

方式 2: 从 HuggingFace 网页直接下载
  1. 访问 https://huggingface.co/{model_id}/tree/main
  2. 下载所有文件到 {cache_dir / local_dir_name}

方式 3: 使用国内镜像 (推荐)
  set HF_ENDPOINT=https://hf-mirror.com
  然后重新运行

下载完成后，设置环境变量指向本地目录:
  set OPC_EMBEDDING_MODEL={cache_dir / local_dir_name}
  或直接把路径放到代码调用处
"""
    # Windows 终端默认 GBK，中文可能乱码 — 强制用 utf-8 写 stderr
    import sys
    try:
        if hasattr(sys.stderr, "buffer"):
            sys.stderr.buffer.write(hint.encode("utf-8", errors="replace"))
            sys.stderr.buffer.flush()
        else:
            sys.stderr.write(hint)
    except Exception:
        # 最后的退路：用 ascii 降级输出
        sys.stderr.write(hint.encode("ascii", errors="replace").decode("ascii"))


def _load_minilm():
    """加载 ChromaDB 内置的 ONNXMiniLM_L6_V2（默认模型）"""
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
    return ONNXMiniLM_L6_V2(), 384


def _load_sentence_transformer(model_id: str, cache_dir: Path):
    """加载 sentence-transformers 模型（bge-m3 等）

    返回一个适配 ChromaDB EmbeddingFunction 接口的对象和向量维度
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError(
            "加载 bge-m3 等模型需要安装 sentence-transformers。\n"
            "请运行: pip install sentence-transformers"
        ) from e

    # 如果是本地路径，直接加载；否则从 HuggingFace 下载
    model_path = Path(model_id)
    if model_path.exists() and model_path.is_dir():
        model = SentenceTransformer(str(model_path), cache_folder=str(cache_dir))
    else:
        model = SentenceTransformer(model_id, cache_folder=str(cache_dir))

    # 包装成 ChromaDB EmbeddingFunction 接口
    class _STEmbeddingFunction:
        def __init__(self, st_model):
            self._model = st_model

        def __call__(self, input):  # ChromaDB 要求参数名为 input
            # sentence-transformers 返回 numpy array，转成 list
            embeddings = self._model.encode(
                input,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embeddings.tolist()

        def name(self):  # ChromaDB 0.5+ 要求
            return f"sentence-transformer-{model_id}"

    dim = model.get_sentence_embedding_dimension()
    return _STEmbeddingFunction(model), dim


def get_embedding_function():
    """获取全局 embedding 函数（懒加载单例）"""
    global _EMBEDDING_FN, _CURRENT_MODEL_ID, _CURRENT_DIMENSION
    if _EMBEDDING_FN is not None:
        return _EMBEDDING_FN

    cache_dir = _ensure_cache_dir()
    model_id = _resolve_model_id(_DEFAULT_MODEL)

    try:
        if model_id == "ONNXMiniLM_L6_V2":
            _EMBEDDING_FN, _CURRENT_DIMENSION = _load_minilm()
            _CURRENT_MODEL_ID = model_id
        else:
            _EMBEDDING_FN, _CURRENT_DIMENSION = _load_sentence_transformer(model_id, cache_dir)
            _CURRENT_MODEL_ID = model_id
    except Exception as e:
        _print_manual_download_hint(model_id, cache_dir, e)
        raise

    return _EMBEDDING_FN


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量生成文本 embedding"""
    fn = get_embedding_function()
    return fn(texts)


def embed_query(text: str) -> list[float]:
    """生成单条查询 embedding"""
    results = embed_texts([text])
    return results[0]


def get_model_info() -> tuple[str, int]:
    """返回当前使用的模型名和向量维度"""
    if _CURRENT_MODEL_ID is None:
        # 未加载时先初始化
        get_embedding_function()
    return _CURRENT_MODEL_ID or "unknown", _CURRENT_DIMENSION or 0


# 为向后兼容保留这两个常量（动态解析）
def _get_model_name() -> str:
    return _resolve_model_id(_DEFAULT_MODEL)


def _get_default_dimension() -> int:
    return _MODEL_DIMENSIONS.get(_get_model_name(), 0)


EMBEDDING_MODEL_NAME = _get_model_name()
# 维度在加载后才精确确定；默认 MiniLM 为 384 维。
EMBEDDING_DIMENSION = _get_default_dimension()
