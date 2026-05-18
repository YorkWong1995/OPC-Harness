"""Git tool implementations for Agent."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitToolsMixin:
    def _tool_git_status(self, porcelain: bool = True) -> str:
        args = ["status", "--short"] if porcelain else ["status"]
        return self._run_git(args)

    def _tool_git_diff(self, cached: bool = False, path: str | None = None) -> str:
        args = ["diff"]
        if cached:
            args.append("--cached")
        if path:
            target = self._resolve_safe_path(path)
            args.extend(["--", str(target.relative_to((self.project_dir or Path.cwd()).resolve()))])
        return self._run_git(args)

    def _tool_git_log(self, limit: int = 5) -> str:
        bounded_limit = max(1, min(int(limit), 50))
        return self._run_git(["log", "--oneline", "-n", str(bounded_limit)])

    def _run_git(self, args: list[str]) -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output = f"{output}\n[stderr]\n{result.stderr.strip()}" if output else f"[stderr]\n{result.stderr.strip()}"
        if result.returncode != 0:
            output = f"{output}\n[exit code: {result.returncode}]" if output else f"[exit code: {result.returncode}]"
        return output or "(无输出)"
