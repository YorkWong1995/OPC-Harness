"""RAG (Retrieval-Augmented Generation) 知识检索模块

支持从外部文档中检索相关信息，增强 Agent 的上下文理解能力。
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple
import re


class SimpleRAG:
    """简单的 RAG 实现，基于关键词匹配和文本分块"""

    def __init__(self, docs_dir: Path, chunk_size: int = 1000, overlap: int = 200):
        """
        初始化 RAG 系统

        Args:
            docs_dir: 文档目录路径
            chunk_size: 文本分块大小（字符数）
            overlap: 分块重叠大小（字符数）
        """
        self.docs_dir = Path(docs_dir)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: List[Dict] = []
        self._index_documents()

    def _index_documents(self):
        """索引文档目录中的所有文本文件"""
        if not self.docs_dir.exists():
            print(f"[RAG] 警告：文档目录不存在: {self.docs_dir}")
            return

        # 支持的文件类型
        extensions = [".md", ".txt", ".h", ".cpp", ".c", ".py", ".rst"]

        for ext in extensions:
            for file_path in self.docs_dir.rglob(f"*{ext}"):
                try:
                    self._index_file(file_path)
                except Exception as e:
                    print(f"[RAG] 索引文件失败 {file_path}: {e}")

        print(f"[RAG] 索引完成，共 {len(self.chunks)} 个文本块")

    def _index_file(self, file_path: Path):
        """索引单个文件"""
        try:
            # 尝试多种编码
            content = None
            for encoding in ["utf-8", "gbk", "gb2312", "latin-1"]:
                try:
                    content = file_path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                print(f"[RAG] 无法读取文件（编码问题）: {file_path}")
                return

            # 分块
            chunks = self._split_text(content)

            # 存储分块信息
            for i, chunk_text in enumerate(chunks):
                self.chunks.append({
                    "file": str(file_path.relative_to(self.docs_dir)),
                    "chunk_id": i,
                    "text": chunk_text,
                    "keywords": self._extract_keywords(chunk_text),
                })

        except Exception as e:
            print(f"[RAG] 索引文件异常 {file_path}: {e}")

    def _split_text(self, text: str) -> List[str]:
        """将文本分块"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # 尝试在句子边界分割
            if end < len(text):
                # 查找最后一个句号、换行或空格
                for sep in ["\n\n", "\n", ". ", "。", " "]:
                    last_sep = chunk.rfind(sep)
                    if last_sep > self.chunk_size * 0.7:  # 至少保留70%
                        chunk = text[start:start + last_sep + len(sep)]
                        break

            chunks.append(chunk.strip())
            start += len(chunk) - self.overlap

        return chunks

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简单实现：提取标识符和常见技术术语）"""
        # 提取标识符（变量名、函数名等）
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', text)

        # 转小写并去重
        keywords = list(set(word.lower() for word in identifiers))

        return keywords[:50]  # 限制关键词数量

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        搜索相关文档块

        Args:
            query: 查询字符串
            top_k: 返回前 k 个最相关的结果

        Returns:
            相关文档块列表，每个元素包含 file, chunk_id, text, score
        """
        if not self.chunks:
            return []

        # 提取查询关键词
        query_keywords = self._extract_keywords(query)
        query_lower = query.lower()

        # 计算每个块的相关性分数
        scored_chunks = []
        for chunk in self.chunks:
            score = 0

            # 1. 关键词匹配
            matching_keywords = set(query_keywords) & set(chunk["keywords"])
            score += len(matching_keywords) * 2

            # 2. 文本包含查询词
            chunk_lower = chunk["text"].lower()
            for keyword in query_keywords:
                if keyword in chunk_lower:
                    score += 1

            # 3. 完整查询字符串匹配
            if query_lower in chunk_lower:
                score += 5

            if score > 0:
                scored_chunks.append({
                    **chunk,
                    "score": score,
                })

        # 按分数排序
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)

        return scored_chunks[:top_k]

    def get_context(self, query: str, max_tokens: int = 2000) -> str:
        """
        获取查询相关的上下文文本

        Args:
            query: 查询字符串
            max_tokens: 最大返回字符数（近似 token 数）

        Returns:
            格式化的上下文文本
        """
        results = self.search(query, top_k=10)

        if not results:
            return "未找到相关文档。"

        context_parts = ["# 相关文档片段\n"]
        current_length = len(context_parts[0])

        for i, result in enumerate(results):
            chunk_text = result["text"]
            header = f"\n## 片段 {i+1} (来源: {result['file']}, 相关度: {result['score']})\n\n"
            chunk_with_header = header + chunk_text + "\n"

            if current_length + len(chunk_with_header) > max_tokens:
                break

            context_parts.append(chunk_with_header)
            current_length += len(chunk_with_header)

        return "".join(context_parts)


def create_rag_for_project(project_dir: Path) -> SimpleRAG | None:
    """
    为项目创建 RAG 实例

    查找项目中的文档目录（docs, documentation, SDK/docs 等）

    Args:
        project_dir: 项目根目录

    Returns:
        RAG 实例，如果没有找到文档目录则返回 None
    """
    # 尝试使用 BM25RAG（如果可用）
    try:
        from .rag_bm25 import create_rag_for_project as create_bm25_rag
        return create_bm25_rag(project_dir, use_bm25=True)
    except ImportError:
        pass  # 回退到 SimpleRAG

    # 常见文档目录名称
    doc_dir_names = ["docs", "documentation", "doc", "SDK/docs", "api_docs"]

    for dir_name in doc_dir_names:
        docs_path = project_dir / dir_name
        if docs_path.exists() and docs_path.is_dir():
            print(f"[RAG] 找到文档目录: {docs_path}")
            return SimpleRAG(docs_path)

    # 尝试查找 SDK 目录中的 docs
    for sdk_dir in project_dir.rglob("*SDK*"):
        if sdk_dir.is_dir():
            docs_path = sdk_dir / "docs"
            if docs_path.exists():
                print(f"[RAG] 找到 SDK 文档目录: {docs_path}")
                return SimpleRAG(docs_path)

    print(f"[RAG] 未找到文档目录")
    return None
