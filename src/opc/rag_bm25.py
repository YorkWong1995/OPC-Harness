"""增强版 RAG：集成 BM25 检索

改进点：
1. 使用 BM25 算法替代简单关键词匹配
2. 支持中文分词（jieba）
3. 更准确的相关性评分
"""

from pathlib import Path
from typing import List, Dict
import re

try:
    from rank_bm25 import BM25Okapi
    import jieba
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("[RAG] 警告：rank-bm25 或 jieba 未安装，将使用简单检索")

from .rag import SimpleRAG


class BM25RAG(SimpleRAG):
    """基于 BM25 的 RAG 实现

    相比 SimpleRAG 的改进：
    1. 使用 BM25 算法计算相关性
    2. 支持中文分词
    3. 更准确的检索结果
    """

    def __init__(self, docs_dir: Path, chunk_size: int = 1000, overlap: int = 200):
        super().__init__(docs_dir, chunk_size, overlap)

        if BM25_AVAILABLE:
            self._build_bm25_index()
        else:
            print("[RAG] BM25 不可用，回退到简单检索")

    def _build_bm25_index(self):
        """构建 BM25 索引"""
        if not self.chunks:
            self.bm25 = None
            return

        # 为每个文档块分词
        tokenized_corpus = []
        for chunk in self.chunks:
            tokens = self._tokenize(chunk["text"])
            tokenized_corpus.append(tokens)

        # 构建 BM25 索引
        self.bm25 = BM25Okapi(tokenized_corpus)
        print(f"[RAG] BM25 索引构建完成")

    def _tokenize(self, text: str) -> List[str]:
        """分词：支持中英文混合

        Args:
            text: 输入文本

        Returns:
            分词结果列表
        """
        tokens = []

        # 1. 提取英文标识符（变量名、函数名等）
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', text)
        tokens.extend([word.lower() for word in identifiers])

        # 2. 中文分词
        chinese_text = re.sub(r'[a-zA-Z0-9_]+', ' ', text)  # 移除英文
        chinese_words = jieba.lcut(chinese_text)
        tokens.extend([word.strip() for word in chinese_words if len(word.strip()) > 1])

        # 3. 提取技术关键词（大写开头）
        tech_terms = re.findall(r'\b[A-Z][a-zA-Z0-9]+\b', text)
        tokens.extend([word.lower() for word in tech_terms])

        return tokens

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """使用 BM25 搜索相关文档块

        Args:
            query: 查询字符串
            top_k: 返回前 k 个最相关的结果

        Returns:
            相关文档块列表，每个元素包含 file, chunk_id, text, score
        """
        if not self.chunks:
            return []

        # 如果 BM25 不可用，回退到简单检索
        if not BM25_AVAILABLE or not hasattr(self, 'bm25') or self.bm25 is None:
            return super().search(query, top_k)

        # 查询分词
        query_tokens = self._tokenize(query)

        # BM25 评分
        scores = self.bm25.get_scores(query_tokens)

        # 获取 top_k 结果
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回有相关性的结果
                results.append({
                    **self.chunks[idx],
                    "score": float(scores[idx]),
                })

        return results


def create_rag_for_project(project_dir: Path, use_bm25: bool = True) -> SimpleRAG | BM25RAG | None:
    """为项目创建 RAG 实例

    Args:
        project_dir: 项目根目录
        use_bm25: 是否使用 BM25（如果可用）

    Returns:
        RAG 实例，如果没有找到文档目录则返回 None
    """
    # 常见文档目录名称
    doc_dir_names = ["docs", "documentation", "doc", "SDK/docs", "api_docs"]

    for dir_name in doc_dir_names:
        docs_path = project_dir / dir_name
        if docs_path.exists() and docs_path.is_dir():
            print(f"[RAG] 找到文档目录: {docs_path}")

            # 优先使用 BM25RAG
            if use_bm25 and BM25_AVAILABLE:
                return BM25RAG(docs_path)
            else:
                return SimpleRAG(docs_path)

    # 尝试查找 SDK 目录中的 docs
    for sdk_dir in project_dir.rglob("*SDK*"):
        if sdk_dir.is_dir():
            docs_path = sdk_dir / "docs"
            if docs_path.exists():
                print(f"[RAG] 找到 SDK 文档目录: {docs_path}")

                if use_bm25 and BM25_AVAILABLE:
                    return BM25RAG(docs_path)
                else:
                    return SimpleRAG(docs_path)

    print(f"[RAG] 未找到文档目录")
    return None
