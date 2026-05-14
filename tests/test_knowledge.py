"""测试 Knowledge 系统：BM25 索引构建/查询、chunker 分块逻辑"""

import tempfile
from pathlib import Path

from opc.knowledge.bm25_index import BM25Index, tokenize
from opc.knowledge.chunker import (
    CodeChunker,
    ConfigChunker,
    DocChunker,
    chunk_file,
    detect_language,
)
from opc.knowledge.models import Chunk


# ── tokenize ──────────────────────────────────────────────


def test_tokenize_chinese():
    """中文分词"""
    tokens = tokenize("机器学习是人工智能的分支")
    assert len(tokens) > 0
    assert all(isinstance(t, str) for t in tokens)


def test_tokenize_english():
    """英文分词（按空格）"""
    tokens = tokenize("hello world foo bar")
    assert "hello" in tokens
    assert "world" in tokens


def test_tokenize_mixed():
    """中英混合分词"""
    tokens = tokenize("使用Python进行开发")
    assert len(tokens) > 0
    # 应包含 python（小写化）
    assert "python" in tokens


def test_tokenize_empty():
    """空字符串返回空列表"""
    assert tokenize("") == []


# ── BM25Index ─────────────────────────────────────────────


def _make_chunk(content: str, file_path: str = "test.py", **kw) -> Chunk:
    return Chunk(
        chunk_id=kw.get("chunk_id", f"{file_path}::L1-L2"),
        file_path=file_path,
        start_line=kw.get("start_line", 1),
        end_line=kw.get("end_line", 2),
        content=content,
        language=kw.get("language", "python"),
        source_name=kw.get("source_name", "test"),
    )


def test_bm25_build_and_query():
    """构建索引后可查询"""
    chunks = [
        _make_chunk("Python是一种编程语言", chunk_id="a::L1-L2"),
        _make_chunk("Java是一种编程语言", chunk_id="b::L1-L2"),
        _make_chunk("机器学习是人工智能的分支", chunk_id="c::L1-L2"),
        _make_chunk("数据库管理系统的设计", chunk_id="d::L1-L2"),
        _make_chunk("网络协议与通信原理", chunk_id="e::L1-L2"),
    ]
    idx = BM25Index()
    idx.build(chunks)
    assert idx.bm25 is not None
    assert len(idx.chunks) == 5

    results = idx.query("Python编程", top_k=5)
    assert len(results) > 0
    # Python 相关结果应排在前面
    assert results[0].chunk.chunk_id.startswith("a")
    assert results[0].score > 0
    assert results[0].source == "bm25"


def test_bm25_query_no_match():
    """查询不匹配的内容返回空"""
    chunks = [_make_chunk("Python是一种编程语言")]
    idx = BM25Index()
    idx.build(chunks)
    # 用完全不相关的中文查询
    results = idx.query("量子力学薛定谔方程", top_k=5)
    # 可能没有 >0 分数的结果
    for r in results:
        assert r.score > 0


def test_bm25_query_before_build():
    """未构建索引时查询返回空列表"""
    idx = BM25Index()
    assert idx.query("test") == []


def test_bm25_top_k_limit():
    """top_k 限制返回数量"""
    chunks = [_make_chunk(f"内容{i}", chunk_id=f"f{i}::L1-L2") for i in range(10)]
    idx = BM25Index()
    idx.build(chunks)
    results = idx.query("内容", top_k=3)
    assert len(results) <= 3


def test_bm25_save_and_load(tmp_path):
    """持久化与加载"""
    chunks = [
        _make_chunk("深度学习模型训练", chunk_id="a::L1-L2"),
        _make_chunk("自然语言处理技术", chunk_id="b::L1-L2"),
        _make_chunk("计算机视觉应用", chunk_id="c::L1-L2"),
        _make_chunk("网络协议分析", chunk_id="d::L1-L2"),
    ]
    idx = BM25Index()
    idx.build(chunks)
    idx.save(tmp_path / "bm25_store")

    # 加载
    idx2 = BM25Index()
    idx2.load(tmp_path / "bm25_store")
    assert idx2.bm25 is not None
    assert len(idx2.chunks) == 4

    results = idx2.query("深度学习", top_k=5)
    assert len(results) > 0
    assert results[0].chunk.chunk_id.startswith("a")


# ── detect_language ───────────────────────────────────────


def test_detect_language_python():
    assert detect_language("foo.py") == "python"


def test_detect_language_javascript():
    assert detect_language("app.js") == "javascript"


def test_detect_language_markdown():
    assert detect_language("readme.md") == "markdown"


def test_detect_language_unknown():
    assert detect_language("foo.xyz") is None


def test_detect_language_cpp():
    assert detect_language("utils.hpp") == "cpp"


# ── CodeChunker ───────────────────────────────────────────


_PYTHON_CODE = '''\
def foo():
    return 1

def bar():
    return 2

class MyClass:
    pass
'''


def test_code_chunker_python():
    """Python 代码按 def/class 切分"""
    chunker = CodeChunker(target_lines=100, min_lines=5)
    chunks = chunker.chunk_file("test.py", _PYTHON_CODE, "python", "src")
    assert len(chunks) >= 1
    # 所有 chunk 应包含内容
    for c in chunks:
        assert c.content.strip()
        assert c.language == "python"
        assert c.source_name == "src"


def test_code_chunker_small_file():
    """小于 min_lines 的文件返回单个 chunk"""
    chunker = CodeChunker(target_lines=100, min_lines=50)
    content = "x = 1\ny = 2\n"
    chunks = chunker.chunk_file("tiny.py", content, "python", "src")
    assert len(chunks) == 1
    assert "x = 1" in chunks[0].content


_BRACE_CODE = '''\
public class Hello {
    public static void main() {
        System.out.println("hi");
    }

}
'''


def test_code_chunker_brace_language():
    """大括号语言按 } 后空行切分"""
    chunker = CodeChunker(target_lines=100, min_lines=5)
    chunks = chunker.chunk_file("Hello.java", _BRACE_CODE, "java", "src")
    assert len(chunks) >= 1
    for c in chunks:
        assert c.language == "java"


def test_code_chunker_blank_line_fallback():
    """未知语言按空行切分"""
    chunker = CodeChunker(target_lines=100, min_lines=5)
    content = "line1\nline2\n\nline3\nline4\n"
    chunks = chunker.chunk_file("f.abc", content, "unknown_lang", "src")
    assert len(chunks) >= 1


def test_code_chunker_window_split():
    """超大区块触发窗口切分"""
    chunker = CodeChunker(target_lines=10, min_lines=5, overlap=2)
    # 生成无空行的长内容
    content = "\n".join(f"x = {i}" for i in range(50))
    chunks = chunker.chunk_file("big.py", content, "python", "src")
    assert len(chunks) > 1


# ── DocChunker ────────────────────────────────────────────


_MARKDOWN_DOC = '''\
# Title

Intro paragraph.

## Section A

Content of section A.

## Section B

Content of section B.
'''


def test_doc_chunker_markdown():
    """Markdown 按标题切分"""
    chunker = DocChunker(target_lines=200, overlap=50)
    chunks = chunker.chunk_file("doc.md", _MARKDOWN_DOC, "markdown", "docs")
    assert len(chunks) >= 2
    for c in chunks:
        assert c.language == "markdown"
        assert c.source_name == "docs"


def test_doc_chunker_markdown_no_headings():
    """无标题 Markdown 退回窗口切分"""
    chunker = DocChunker(target_lines=5, overlap=1)
    content = "\n".join(f"Line {i}" for i in range(20))
    chunks = chunker.chunk_file("flat.md", content, "markdown", "docs")
    assert len(chunks) > 1


def test_doc_chunker_rst():
    """RST 按章节标题切分"""
    chunker = DocChunker(target_lines=200, overlap=50)
    content = "Title\n=====\n\nIntro.\n\nSection A\n---------\n\nContent A.\n"
    chunks = chunker.chunk_file("doc.rst", content, "rst", "docs")
    assert len(chunks) >= 1
    for c in chunks:
        assert c.language == "rst"


def test_doc_chunker_window_fallback():
    """纯文本走窗口切分"""
    chunker = DocChunker(target_lines=5, overlap=1)
    content = "\n".join(f"Line {i}" for i in range(20))
    chunks = chunker.chunk_file("doc.txt", content, "text", "docs")
    assert len(chunks) > 1


def test_config_chunker_json_top_level_keys():
    """JSON 按顶层 key 分块"""
    content = '{\n  "alpha": {\n    "enabled": true\n  },\n  "beta": [1, 2]\n}\n'
    chunks = ConfigChunker().chunk_file("config.json", content, "json", "cfg")
    assert len(chunks) == 2
    assert '"alpha"' in chunks[0].content
    assert '"beta"' in chunks[1].content


def test_config_chunker_yaml_top_level_keys():
    """YAML 按顶层 key 分块"""
    content = "alpha:\n  enabled: true\nbeta:\n  - 1\n  - 2\n"
    chunks = ConfigChunker().chunk_file("config.yaml", content, "yaml", "cfg")
    assert len(chunks) == 2
    assert chunks[0].content.startswith("alpha:")
    assert chunks[1].content.startswith("beta:")


# ── chunk_file (集成) ────────────────────────────────────


def test_chunk_file_python():
    """自动检测 Python 并分块"""
    chunks = chunk_file("app.py", _PYTHON_CODE, "src")
    assert len(chunks) >= 1
    assert chunks[0].language == "python"


def test_chunk_file_markdown():
    """自动检测 Markdown 并分块"""
    chunks = chunk_file("readme.md", _MARKDOWN_DOC, "docs")
    assert len(chunks) >= 1
    assert chunks[0].language == "markdown"


def test_chunk_file_unknown_ext():
    """未知扩展名返回空列表"""
    assert chunk_file("data.bin", "binary content", "src") == []


def test_chunk_file_passes_kwargs():
    """chunk_file 传递 kwargs 到对应 chunker"""
    chunks = chunk_file("tiny.py", "x=1\n", "src", min_lines=100)
    assert len(chunks) == 1
