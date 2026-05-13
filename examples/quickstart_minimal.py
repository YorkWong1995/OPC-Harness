"""Minimal safe quickstart for the current OPC CLI workflow."""

from __future__ import annotations

import argparse
import subprocess
import sys


def build_command(task: str, project: str, auto_confirm: bool) -> list[str]:
    command = [sys.executable, "-m", "opc.cli", "run", task, "--project", project]
    if auto_confirm:
        command.append("--auto-confirm")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the minimal OPC PM -> Engineer -> QA workflow.")
    parser.add_argument(
        "--task",
        default="为示例项目补充一个最小 README 变更，并给出验收记录",
        help="Task passed to opc run.",
    )
    parser.add_argument("--project", default="quickstart-minimal", help="Workspace project name.")
    parser.add_argument("--auto-confirm", action="store_true", help="Skip interactive confirmations.")
    parser.add_argument("--execute", action="store_true", help="Actually run opc.cli; default only prints the command.")
    args = parser.parse_args()

    command = build_command(args.task, args.project, args.auto_confirm)
    print(" ".join(command))
    if not args.execute:
        print("Dry run only. Add --execute to trigger the workflow.")
        return 0

    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
