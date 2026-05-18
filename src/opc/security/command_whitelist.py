"""Command allowlist and audit helpers."""

from __future__ import annotations

COMMAND_WHITELIST = {
    "python", "pip", "npm", "node", "git", "pytest", "eslint", "npx", "cargo", "go",
    "gcc", "g++", "cmake", "make", "cl", "clang", "clang++", "nmake", "msbuild",
}

DANGEROUS_PARAMS: dict[str, list[str]] = {
    "git": ["push --force", "reset --hard", "clean -f", "branch -D"],
    "pip": ["install --pre", "install --force-reinstall"],
    "npm": ["publish", "unpublish"],
    "rm": ["-rf", "-r"],
}


def check_interactive_command(command: str) -> str | None:
    lowered = command.lower()
    interactive_markers = [
        "npm create ", "pnpm create ", "yarn create ", "bun create ",
        "npm init ", "pnpm init ", "yarn init ", "npx create-",
        "bunx create-", "cargo new ", "cargo init ",
    ]
    non_interactive_flags = [
        "--yes", " -y", "--skip-install", "--defaults", "--non-interactive", "--ci",
    ]
    if any(marker in lowered for marker in interactive_markers) and not any(
        flag in lowered for flag in non_interactive_flags
    ):
        return (
            "错误：此命令需要交互式输入，但 run_command 工具不支持交互。\n"
            "建议：添加非交互式标志（如 --yes、-y、--defaults、--non-interactive）。\n"
            f"示例：{command} --yes"
        )
    return None


def match_dangerous_params(cmd_name: str, full_command: str) -> list[str]:
    patterns = DANGEROUS_PARAMS.get(cmd_name, [])
    lowered = full_command.lower()
    return [pattern for pattern in patterns if pattern in lowered]
