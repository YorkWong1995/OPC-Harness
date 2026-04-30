"""索引构建编排器：文件发现 → 分块 → BM25 → 向量 → 元数据"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .models import Chunk, IndexMeta, EXTENSION_MAP, SKIP_DIRS
from .chunker import chunk_file
from .bm25_index import BM25Index
from .vector_store import VectorStore
from .embedder import EMBEDDING_MODEL_NAME


class Indexer:
    """索引构建编排器"""

    def __init__(self, index_name: str, index_root: Path):
        self.index_name = index_name
        self.index_root = index_root

    @property
    def meta_path(self) -> Path:
        return self.index_root / "meta.json"

    @property
    def chroma_path(self) -> Path:
        return self.index_root / "chroma"

    @property
    def bm25_path(self) -> Path:
        return self.index_root / "bm25"

    def build(
        self,
        source_dirs: list[Path],
        extensions: list[str] | None = None,
        overwrite: bool = False,
        verbose: bool = False,
    ) -> IndexMeta:
        """构建完整索引

        Args:
            source_dirs: 要索引的源目录列表
            extensions: 限制的文件扩展名（如 ['.py', '.md']）
            overwrite: 是否覆盖已有索引
            verbose: 是否输出详细信息
        """
        start_time = time.time()

        if overwrite:
            self._clean_index()

        self.index_root.mkdir(parents=True, exist_ok=True)

        # 1. 发现文件
        ext_filter = set(extensions) if extensions else set(EXTENSION_MAP.keys())
        files = self._discover_files(source_dirs, ext_filter)
        if verbose:
            print(f"  发现 {len(files)} 个文件")

        # 2. 分块
        all_chunks: list[Chunk] = []
        for file_path, source_name in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # 相对路径：基于所在源目录
            try:
                rel_path = str(file_path.relative_to(source_name))
            except ValueError:
                rel_path = file_path.name
            chunks = chunk_file(rel_path, content, source_name=source_name.name)
            all_chunks.extend(chunks)

        if verbose:
            print(f"  生成 {len(all_chunks)} 个分块")

        if not all_chunks:
            meta = IndexMeta(
                index_name=self.index_name,
                source_dirs=[str(d) for d in source_dirs],
                total_files=len(files),
                total_chunks=0,
                embedding_model=EMBEDDING_MODEL_NAME,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self._save_meta(meta)
            return meta

        # 3. 构建 BM25 索引
        if verbose:
            print("  构建 BM25 索引...")
        bm25 = BM25Index()
        bm25.build(all_chunks)
        bm25.save(self.bm25_path)

        # 4. 构建向量索引
        if verbose:
            print("  构建向量索引...")
        vs = VectorStore(self.chroma_path)
        vs.create_collection(self.index_name)
        vs.add_chunks(all_chunks)

        # 5. 保存元数据
        elapsed = time.time() - start_time
        meta = IndexMeta(
            index_name=self.index_name,
            source_dirs=[str(d) for d in source_dirs],
            total_files=len(files),
            total_chunks=len(all_chunks),
            embedding_model=EMBEDDING_MODEL_NAME,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._save_meta(meta)

        if verbose:
            print(f"  索引完成，耗时 {elapsed:.1f}s")

        return meta

    def _discover_files(self, source_dirs: list[Path], ext_filter: set[str]) -> list[tuple[Path, Path]]:
        """递归发现文件，返回 (文件路径, 所属源目录) 列表"""
        files = []
        for source_dir in source_dirs:
            source_dir = source_dir.resolve()
            if source_dir.is_file():
                ext = source_dir.suffix.lower()
                if ext in ext_filter:
                    files.append((source_dir, source_dir.parent))
                continue
            for file_path in source_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                # 跳过忽略目录
                parts = file_path.relative_to(source_dir).parts
                if any(part in SKIP_DIRS for part in parts):
                    continue
                ext = file_path.suffix.lower()
                if ext in ext_filter:
                    files.append((file_path, source_dir))
        return files

    def _clean_index(self):
        """清理已有索引"""
        import shutil
        if self.index_root.exists():
            shutil.rmtree(self.index_root, ignore_errors=True)

    def _save_meta(self, meta: IndexMeta):
        """保存索引元数据"""
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(
            json.dumps({
                "index_name": meta.index_name,
                "source_dirs": meta.source_dirs,
                "total_files": meta.total_files,
                "total_chunks": meta.total_chunks,
                "embedding_model": meta.embedding_model,
                "created_at": meta.created_at,
                "updated_at": meta.updated_at,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def load_meta(index_root: Path) -> IndexMeta | None:
        """加载索引元数据"""
        meta_path = index_root / "meta.json"
        if not meta_path.exists():
            return None
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return IndexMeta(**data)
