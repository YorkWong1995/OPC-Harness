"""语言感知的文件分块器：代码按函数/类边界，文档按标题/窗口"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Chunk, EXTENSION_MAP, CODE_LANGUAGES, DOC_LANGUAGES


class CodeChunker:
    """按函数/类边界分块代码文件"""

    def __init__(self, target_lines: int = 100, min_lines: int = 20, overlap: int = 10):
        self.target_lines = target_lines
        self.min_lines = min_lines
        self.overlap = overlap

    def chunk_file(self, file_path: str, content: str, language: str, source_name: str) -> list[Chunk]:
        lines = content.split("\n")
        if len(lines) <= self.min_lines:
            return [self._make_chunk(file_path, lines, 1, len(lines), language, source_name)]

        split_points = self._find_split_points(lines, language)
        chunks = self._split_by_points(lines, split_points, file_path, language, source_name)
        return chunks

    def _find_split_points(self, lines: list[str], language: str) -> list[int]:
        points = []
        if language == "python":
            points = self._python_splits(lines)
        elif language in {"cpp", "c", "java", "csharp", "go", "rust", "javascript", "typescript"}:
            points = self._brace_splits(lines)
        else:
            points = self._blank_line_splits(lines)
        return sorted(set(points))

    def _python_splits(self, lines: list[str]) -> list[int]:
        """在顶层 def/class 之后的首个空行处切分"""
        points = []
        in_top_level_def = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 顶层定义开始
            if re.match(r"^(def |class |async def )", stripped) and not line[0].isspace():
                in_top_level_def = True
                continue
            # 顶层定义后的空行 = 切分点
            if in_top_level_def and stripped == "":
                points.append(i)
                in_top_level_def = False
        return points

    def _brace_splits(self, lines: list[str]) -> list[int]:
        """在列0位置 } 后的空行处切分（C/C++/Java/Go 风格）"""
        points = []
        for i, line in enumerate(lines):
            if line.startswith("}") and line.strip() == "}":
                # 向后找空行
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip() == "":
                        points.append(j)
                        break
        return points

    def _blank_line_splits(self, lines: list[str]) -> list[int]:
        """在空行处切分"""
        points = []
        for i, line in enumerate(lines):
            if line.strip() == "" and i > 0 and lines[i - 1].strip() != "":
                points.append(i)
        return points

    def _split_by_points(
        self, lines: list[str], split_points: list[int],
        file_path: str, language: str, source_name: str,
    ) -> list[Chunk]:
        if not split_points:
            # 无切分点：按固定窗口切分
            return self._window_split(lines, file_path, language, source_name)

        # 构建区间
        boundaries = [0] + split_points + [len(lines)]
        chunks = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            chunk_lines = lines[start:end]

            # 如果区块太大，继续窗口切分
            if len(chunk_lines) > self.target_lines * 2:
                sub_chunks = self._window_split(
                    chunk_lines, file_path, language, source_name,
                    line_offset=start,
                )
                chunks.extend(sub_chunks)
            else:
                chunks.append(self._make_chunk(
                    file_path, chunk_lines, start + 1, end, language, source_name,
                ))

        # 合并过小的区块
        chunks = self._merge_small(chunks, file_path, language, source_name)
        return chunks

    def _window_split(
        self, lines: list[str], file_path: str, language: str, source_name: str,
        line_offset: int = 0,
    ) -> list[Chunk]:
        window = self.target_lines
        step = window - self.overlap
        chunks = []
        start = 0
        while start < len(lines):
            end = min(start + window, len(lines))
            chunk_lines = lines[start:end]
            actual_start = line_offset + start
            actual_end = line_offset + end
            chunks.append(self._make_chunk(
                file_path, chunk_lines, actual_start + 1, actual_end, language, source_name,
            ))
            if end >= len(lines):
                break
            start += step
        return chunks

    def _merge_small(
        self, chunks: list[Chunk], file_path: str, language: str, source_name: str,
    ) -> list[Chunk]:
        if not chunks:
            return chunks
        merged = [chunks[0]]
        for chunk in chunks[1:]:
            prev = merged[-1]
            if prev.end_line == chunk.start_line - 1 and (
                len(prev.content.split("\n")) + len(chunk.content.split("\n"))
            ) < self.min_lines * 2:
                # 合并相邻小区块
                new_content = prev.content + "\n" + chunk.content
                merged[-1] = self._make_chunk(
                    file_path, new_content.split("\n"),
                    prev.start_line, chunk.end_line, language, source_name,
                )
            else:
                merged.append(chunk)
        return merged

    def _make_chunk(
        self, file_path: str, lines_or_content, start_line: int, end_line: int,
        language: str, source_name: str,
    ) -> Chunk:
        if isinstance(lines_or_content, list):
            content = "\n".join(lines_or_content)
        else:
            content = lines_or_content
        chunk_id = f"{file_path}::L{start_line}-L{end_line}"
        return Chunk(
            chunk_id=chunk_id,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            language=language,
            source_name=source_name,
        )


class DocChunker:
    """按标题/固定窗口分块文档文件"""

    def __init__(self, target_lines: int = 200, overlap: int = 50):
        self.target_lines = target_lines
        self.overlap = overlap

    def chunk_file(self, file_path: str, content: str, language: str, source_name: str) -> list[Chunk]:
        if language == "markdown":
            return self._markdown_chunks(file_path, content, language, source_name)
        elif language == "rst":
            return self._rst_chunks(file_path, content, language, source_name)
        else:
            return self._window_chunks(file_path, content, language, source_name)

    def _markdown_chunks(self, file_path: str, content: str, language: str, source_name: str) -> list[Chunk]:
        lines = content.split("\n")
        # 找到所有标题行
        heading_indices = []
        for i, line in enumerate(lines):
            if re.match(r"^#{1,6}\s", line):
                heading_indices.append(i)
        if not heading_indices:
            return self._window_chunks(file_path, content, language, source_name)

        # 按标题切分（去重、跳过空段）
        boundaries = sorted(set([0] + heading_indices + [len(lines)]))
        chunks = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            if start >= end:
                continue
            section_lines = lines[start:end]
            # 超长段落再窗口切分
            if len(section_lines) > self.target_lines * 1.5:
                sub_content = "\n".join(section_lines)
                sub_chunks = self._window_chunks(
                    file_path, sub_content, language, source_name,
                    line_offset=start,
                )
                chunks.extend(sub_chunks)
            else:
                chunk_id = f"{file_path}::L{start + 1}-L{end}"
                chunks.append(Chunk(
                    chunk_id=chunk_id,
                    file_path=file_path,
                    start_line=start + 1,
                    end_line=end,
                    content="\n".join(section_lines),
                    language=language,
                    source_name=source_name,
                ))
        return chunks

    def _rst_chunks(self, file_path: str, content: str, language: str, source_name: str) ->Chunk:
        lines = content.split("\n")
        section_indices = [0]
        for i in range(1, len(lines) - 1):
            # RST 标题：上/下划线
            if (
                lines[i - 1].strip()
                and lines[i].strip()
                and len(lines[i].strip()) >= len(lines[i - 1].strip())
                and re.match(r"^[=\-~^\"`]+$", lines[i].strip())
            ):
                section_indices.append(i - 1)
        section_indices.append(len(lines))

        chunks = []
        for i in range(len(section_indices) - 1):
            start = section_indices[i]
            end = section_indices[i + 1]
            section_lines = lines[start:end]
            if len(section_lines) > self.target_lines * 1.5:
                sub_content = "\n".join(section_lines)
                sub_chunks = self._window_chunks(
                    file_path, sub_content, language, source_name, line_offset=start,
                )
                chunks.extend(sub_chunks)
            else:
                chunk_id = f"{file_path}::L{start + 1}-L{end}"
                chunks.append(Chunk(
                    chunk_id=chunk_id,
                    file_path=file_path,
                    start_line=start + 1,
                    end_line=end,
                    content="\n".join(section_lines),
                    language=language,
                    source_name=source_name,
                ))
        return chunks

    def _window_chunks(
        self, file_path: str, content: str, language: str, source_name: str,
        line_offset: int = 0,
    ) -> list[Chunk]:
        lines = content.split("\n")
        window = self.target_lines
        step = window - self.overlap
        chunks = []
        start = 0
        while start < len(lines):
            end = min(start + window, len(lines))
            actual_start = line_offset + start
            actual_end = line_offset + end
            chunk_id = f"{file_path}::L{actual_start + 1}-L{actual_end}"
            chunks.append(Chunk(
                chunk_id=chunk_id,
                file_path=file_path,
                start_line=actual_start + 1,
                end_line=actual_end,
                content="\n".join(lines[start:end]),
                language=language,
                source_name=source_name,
            ))
            if end >= len(lines):
                break
            start += step
        return chunks


def detect_language(file_path: str) -> str | None:
    """根据扩展名检测语言类型"""
    ext = Path(file_path).suffix.lower()
    return EXTENSION_MAP.get(ext)


def chunk_file(file_path: str, content: str, source_name: str, **kwargs) -> list[Chunk]:
    """自动检测语言并分块"""
    language = detect_language(file_path)
    if language is None:
        return []

    if language in CODE_LANGUAGES:
        chunker = CodeChunker(**{k: v for k, v in kwargs.items() if k in ("target_lines", "min_lines", "overlap")})
    elif language in DOC_LANGUAGES:
        chunker = DocChunker(**{k: v for k, v in kwargs.items() if k in ("target_lines", "overlap")})
    else:
        # 配置文件等：作为整体文本窗口切分
        chunker = DocChunker(**{k: v for k, v in kwargs.items() if k in ("target_lines", "overlap")})

    return chunker.chunk_file(file_path, content, language, source_name)
