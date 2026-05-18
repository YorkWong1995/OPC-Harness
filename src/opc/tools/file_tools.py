"""File and search tool implementations for Agent."""

from __future__ import annotations

import re
import shutil
import subprocess


class FileToolsMixin:
    def _tool_read_file(self, path: str) -> str:
        target = self._resolve_safe_path(path)
        if not target.exists():
            return f"错误：文件不存在 {path}"
        if target.is_dir():
            return f"错误：{path} 是目录，不是文件"
        return target.read_text(encoding="utf-8")

    def _tool_write_file(self, path: str, content: str) -> str:
        target = self._resolve_safe_path(path)
        if target.name in {".env", ".env.local", ".env.production"}:
            return "错误：不允许写入环境变量文件"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"已写入 {path}（{len(content)} 字符）"

    def _tool_edit_file(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        target = self._resolve_safe_path(path)
        if not target.exists():
            return f"错误：文件不存在 {path}"
        if target.is_dir():
            return f"错误：{path} 是目录，不是文件"
        if target.name in {".env", ".env.local", ".env.production"}:
            return "错误：不允许编辑环境变量文件"
        try:
            original = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"错误：{path} 不是 UTF-8 文本文件"
        if old_string not in original:
            return "错误：在文件中未找到 old_string。请确认要替换的内容存在。"
        if replace_all:
            count = original.count(old_string)
            updated = original.replace(old_string, new_string)
            target.write_text(updated, encoding="utf-8")
            return f"已更新 {path}（替换了 {count} 处）"
        updated = original.replace(old_string, new_string, 1)
        target.write_text(updated, encoding="utf-8")
        return f"已更新 {path}（替换了 1 处）"

    def _tool_list_files(self, pattern: str = "**/*") -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"
        matches = list(self.project_dir.glob(pattern))
        skip = {"__pycache__", ".git", "node_modules", ".venv", "venv"}
        lines = []
        for path in sorted(matches):
            parts = path.relative_to(self.project_dir).parts
            if any(part in parts for part in skip):
                continue
            kind = "dir" if path.is_dir() else "file"
            lines.append(f"[{kind}] {path.relative_to(self.project_dir)}")
        return "\n".join(lines) if lines else "无匹配文件"

    def _tool_grep(self, pattern: str, file_glob: str = "**/*", case_sensitive: bool = True, limit: int = 200) -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"
        rg_path = shutil.which("rg")
        if rg_path:
            try:
                cmd = [rg_path, "--line-number", "--no-heading", "--color", "never"]
                if not case_sensitive:
                    cmd.append("--ignore-case")
                cmd.extend(["--glob", file_glob, pattern, "."])
                result = subprocess.run(
                    cmd,
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")[:limit]
                    return "\n".join(lines) if lines else "无匹配结果"
                if result.returncode == 1:
                    return "无匹配结果"
            except (subprocess.TimeoutExpired, Exception):
                pass

        try:
            regex = re.compile(pattern, flags=0 if case_sensitive else re.IGNORECASE)
        except re.error as error:
            return f"错误：无效的正则表达式 - {error}"

        matches = []
        skip = {"__pycache__", ".git", "node_modules", ".venv", "venv"}
        for file_path in self.project_dir.glob(file_glob):
            if not file_path.is_file():
                continue
            parts = file_path.relative_to(self.project_dir).parts
            if any(part in parts for part in skip):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                for line_num, line in enumerate(content.splitlines(), start=1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(self.project_dir)
                        matches.append(f"{rel_path}:{line_num}:{line.strip()}")
                        if len(matches) >= limit:
                            break
            except (UnicodeDecodeError, PermissionError):
                continue
            if len(matches) >= limit:
                break
        return "\n".join(matches) if matches else "无匹配结果"
