"""数据模型定义"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    chunk_id: str          # "{file_path}::L{start}-L{end}"
    file_path: str         # 相对于索引根目录
    start_line: int
    end_line: int
    content: str
    language: str          # "python", "cpp", "markdown", "text", etc.
    source_name: str       # 来源目录标识


@dataclass
class IndexMeta:
    index_name: str
    source_dirs: list[str]
    total_files: int
    total_chunks: int
    embedding_model: str
    created_at: str
    updated_at: str


@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float
    source: str            # "vector" or "bm25"
    rank: int = 0


@dataclass
class FusedResult:
    chunk: Chunk
    rrf_score: float = 0.0
    vector_rank: int | None = None
    bm25_rank: int | None = None


# 支持的文件扩展名 → 语言映射
EXTENSION_MAP: dict[str, str] = {
    # 代码
    ".py": "python",
    ".cpp": "cpp", ".cxx": "cpp", ".cc": "cpp",
    ".h": "cpp", ".hpp": "cpp",
    ".c": "c",
    ".java": "java",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".js": "javascript",
    ".ts": "typescript",
    # 文档
    ".md": "markdown",
    ".rst": "rst",
    ".txt": "text",
    # 配置
    ".json": "json",
    ".yaml": "yaml", ".yml": "yaml",
    ".xml": "xml",
    ".toml": "toml",
    ".ini": "ini", ".cfg": "ini",
    # 其他
    ".html": "html",
    ".css": "css",
    ".sh": "shell", ".bat": "shell",
}

# 代码类语言集合
CODE_LANGUAGES = {
    "python", "cpp", "c", "java", "csharp", "go", "rust",
    "javascript", "typescript",
}

# 文档类语言集合
DOC_LANGUAGES = {"markdown", "rst", "text"}

# 索引时跳过的目录名
SKIP_DIRS = {
    "__pycache__", ".git", ".svn", ".hg",
    "node_modules", ".venv", "venv",
    "build", "dist", ".tox", ".mypy_cache",
    ".idea", ".vs", "cmake-build-*",
}
