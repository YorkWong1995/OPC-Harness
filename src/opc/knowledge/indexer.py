"""索引构建编排器：文件发现 → 分块 → BM25 → 向量 → 元数据"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .models import Chunk, IndexMeta, EXTENSION_MAP, SKIP_DIRS
from .chunker import chunk_file
from .bm25_index import BM25Index
from .vector_store import VectorStore
from .embedder import get_model_info
from .import_graph import ImportGraph


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
        incremental: bool = False,
    ) -> IndexMeta:
        """构建完整索引

        Args:
            source_dirs: 要索引的源目录列表
            extensions: 限制的文件扩展名（如 ['.py', '.md']）
            overwrite: 是否覆盖已有索引
            verbose: 是否输出详细信息
            incremental: 是否只重新索引发生变更的文件
        """
        if incremental and not overwrite:
            return self._build_incremental(source_dirs, extensions, verbose)

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
        file_manifest: dict[str, dict] = {}
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
            file_manifest[rel_path] = self._file_signature(file_path, chunks)

        file_dependencies = self._build_file_dependencies(files)

        if verbose:
            print(f"  生成 {len(all_chunks)} 个分块")

        if not all_chunks:
            model_name, _ = get_model_info()
            meta = IndexMeta(
                index_name=self.index_name,
                source_dirs=[str(d) for d in source_dirs],
                total_files=len(files),
                total_chunks=0,
                embedding_model=model_name,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                file_manifest=file_manifest,
                file_dependencies=file_dependencies,
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
        model_name, _ = get_model_info()
        meta = IndexMeta(
            index_name=self.index_name,
            source_dirs=[str(d) for d in source_dirs],
            total_files=len(files),
            total_chunks=len(all_chunks),
            embedding_model=model_name,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            file_manifest=file_manifest,
            file_dependencies=file_dependencies,
        )
        self._save_meta(meta)

        if verbose:
            print(f"  索引完成，耗时 {elapsed:.1f}s")

        return meta

    def _build_incremental(
        self,
        source_dirs: list[Path],
        extensions: list[str] | None = None,
        verbose: bool = False,
    ) -> IndexMeta:
        start_time = time.time()
        previous_meta = self.load_meta(self.index_root)
        bm25 = BM25Index()

        if previous_meta is None or not self.bm25_path.exists():
            if verbose:
                print("  未发现已有索引，执行完整构建...")
            return self.build(source_dirs, extensions, overwrite=False, verbose=verbose)

        self.index_root.mkdir(parents=True, exist_ok=True)
        ext_filter = set(extensions) if extensions else set(EXTENSION_MAP.keys())
        files = self._discover_files(source_dirs, ext_filter)
        previous_manifest = previous_meta.file_manifest or {}
        current_manifest: dict[str, dict] = {}
        current_paths: set[str] = set()
        unchanged_paths: set[str] = set()
        changed_files: list[tuple[Path, Path, str, str]] = []

        for file_path, source_name in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            try:
                rel_path = str(file_path.relative_to(source_name))
            except ValueError:
                rel_path = file_path.name
            current_paths.add(rel_path)
            signature = self._file_signature(file_path)
            current_manifest[rel_path] = signature
            if previous_manifest.get(rel_path, {}).get("hash") == signature["hash"]:
                unchanged_paths.add(rel_path)
            else:
                changed_files.append((file_path, source_name, rel_path, content))

        deleted_paths = set(previous_manifest) - current_paths
        bm25.load(self.bm25_path)
        retained_chunks = [c for c in bm25.chunks if c.file_path in unchanged_paths]
        removed_chunk_ids = [c.chunk_id for c in bm25.chunks if c.file_path in deleted_paths or c.file_path not in unchanged_paths]

        changed_chunks: list[Chunk] = []
        for _, source_name, rel_path, content in changed_files:
            chunks = chunk_file(rel_path, content, source_name=source_name.name)
            changed_chunks.extend(chunks)
            current_manifest[rel_path] = self._signature_from_content(content, chunks)

        all_chunks = retained_chunks + changed_chunks
        if verbose:
            print(f"  增量更新：保留 {len(unchanged_paths)} 个文件，重建 {len(changed_files)} 个文件，删除 {len(deleted_paths)} 个文件")
            print(f"  生成 {len(all_chunks)} 个分块")

        bm25.build(all_chunks)
        bm25.save(self.bm25_path)

        vs = VectorStore(self.chroma_path)
        vs.create_collection(self.index_name)
        vs.delete_chunks(removed_chunk_ids)
        vs.add_chunks(changed_chunks)

        model_name, _ = get_model_info()
        file_dependencies = self._build_file_dependencies(files)
        meta = IndexMeta(
            index_name=self.index_name,
            source_dirs=[str(d) for d in source_dirs],
            total_files=len(current_paths),
            total_chunks=len(all_chunks),
            embedding_model=model_name,
            created_at=previous_meta.created_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
            file_manifest=current_manifest,
            file_dependencies=file_dependencies,
        )
        self._save_meta(meta)

        if verbose:
            elapsed = time.time() - start_time
            print(f"  增量索引完成，耗时 {elapsed:.1f}s")

        return meta

    def _build_file_dependencies(self, files: list[tuple[Path, Path]]) -> dict[str, dict[str, list[str]]]:
        by_source: dict[Path, list[Path]] = {}
        for file_path, source_dir in files:
            if file_path.suffix == ".py":
                by_source.setdefault(source_dir, []).append(file_path)

        result: dict[str, dict[str, list[str]]] = {}
        for source_dir, py_files in by_source.items():
            graph = ImportGraph()
            graph.index_files(py_files, source_dir)
            for file_path in py_files:
                rel_path = self._relative_path(file_path, source_dir)
                dependencies = [self._relative_path(Path(dep), source_dir) for dep in graph.file_dependencies_of(str(file_path))]
                dependents = [self._relative_path(Path(dep), source_dir) for dep in graph.file_dependents_of(str(file_path))]
                result[rel_path] = {
                    "dependencies": sorted(set(dependencies)),
                    "dependents": sorted(set(dependents)),
                }
        return result

    def get_file_dependencies(self, file_path: str) -> dict[str, list[str]]:
        meta = self.load_meta(self.index_root)
        if meta is None:
            return {"dependencies": [], "dependents": []}
        return meta.file_dependencies.get(file_path, {"dependencies": [], "dependents": []})

    @staticmethod
    def _relative_path(file_path: Path, source_dir: Path) -> str:
        try:
            return str(file_path.relative_to(source_dir))
        except ValueError:
            return file_path.name

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

    def _file_signature(self, file_path: Path, chunks: list[Chunk] | None = None) -> dict:
        content = file_path.read_bytes()
        signature = {
            "mtime": file_path.stat().st_mtime,
            "size": file_path.stat().st_size,
            "hash": hashlib.sha256(content).hexdigest(),
        }
        if chunks is not None:
            signature["chunks"] = [c.chunk_id for c in chunks]
        return signature

    def _signature_from_content(self, content: str, chunks: list[Chunk]) -> dict:
        encoded = content.encode("utf-8")
        return {
            "mtime": None,
            "size": len(encoded),
            "hash": hashlib.sha256(encoded).hexdigest(),
            "chunks": [c.chunk_id for c in chunks],
        }

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
                "file_manifest": meta.file_manifest,
                "file_dependencies": meta.file_dependencies,
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
