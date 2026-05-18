"""Build, lint, typecheck, and test tool implementations for Agent."""

from __future__ import annotations

import subprocess
import sys


class BuildToolsMixin:
    def _tool_run_lint(self, target: str | None = None, timeout: int = 120) -> str:
        return self._run_project_tool(self._detect_lint_command(target), timeout, "lint")

    def _tool_run_typecheck(self, target: str | None = None, timeout: int = 120) -> str:
        return self._run_project_tool(self._detect_typecheck_command(target), timeout, "typecheck")

    def _tool_run_build(self, timeout: int = 300) -> str:
        return self._run_project_tool(self._detect_build_command(), timeout, "build")

    def _detect_lint_command(self, target: str | None = None) -> list[str] | None:
        if not self.project_dir:
            return None
        resolved_target = str(self._resolve_safe_path(target).relative_to(self.project_dir.resolve())) if target else "."
        if (self.project_dir / "pyproject.toml").exists() or (self.project_dir / "setup.py").exists():
            return [sys.executable, "-m", "ruff", "check", resolved_target]
        if (self.project_dir / "package.json").exists():
            return ["npx", "eslint", resolved_target]
        return None

    def _detect_typecheck_command(self, target: str | None = None) -> list[str] | None:
        if not self.project_dir:
            return None
        resolved_target = str(self._resolve_safe_path(target).relative_to(self.project_dir.resolve())) if target else "."
        if (self.project_dir / "pyproject.toml").exists() or (self.project_dir / "setup.py").exists():
            return [sys.executable, "-m", "mypy", resolved_target]
        if (self.project_dir / "tsconfig.json").exists():
            return ["npx", "tsc", "--noEmit"]
        return None

    def _detect_build_command(self) -> list[str] | None:
        if not self.project_dir:
            return None
        if (self.project_dir / "pyproject.toml").exists() or (self.project_dir / "setup.py").exists():
            return [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"]
        if (self.project_dir / "package.json").exists():
            return ["npm", "run", "build"]
        if (self.project_dir / "Cargo.toml").exists():
            return ["cargo", "build"]
        return None

    def _run_project_tool(self, command: list[str] | None, timeout: int, label: str) -> str:
        if command is None:
            return f"错误：未检测到可用的 {label} 命令，请确认项目配置"
        bounded_timeout = max(1, min(int(timeout), 1800))
        try:
            result = subprocess.run(
                command,
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=bounded_timeout,
            )
        except subprocess.TimeoutExpired:
            return f"错误：{label} 执行超时（{bounded_timeout}秒）"
        except FileNotFoundError:
            return f"错误：{label} 工具未安装（{command[0]}）"
        return _format_process_output(result)

    def _tool_run_tests(self, target: str | None = None, timeout: int = 300, quiet: bool = True) -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"
        command = [sys.executable, "-m", "pytest"]
        if quiet:
            command.append("-q")
        if target:
            resolved_target = self._resolve_safe_path(target)
            command.append(str(resolved_target.relative_to(self.project_dir.resolve())))
        bounded_timeout = max(1, min(int(timeout), 1800))
        result = subprocess.run(
            command,
            cwd=str(self.project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=bounded_timeout,
        )
        return _format_process_output(result)


def _format_process_output(result: subprocess.CompletedProcess) -> str:
    output = result.stdout.strip()
    if result.stderr.strip():
        output = f"{output}\n[stderr]\n{result.stderr.strip()}" if output else f"[stderr]\n{result.stderr.strip()}"
    if result.returncode != 0:
        output = f"{output}\n[exit code: {result.returncode}]" if output else f"[exit code: {result.returncode}]"
    if len(output) > 12000:
        output = output[:12000] + "\n...[输出已截断]..."
    return output or "(无输出)"
