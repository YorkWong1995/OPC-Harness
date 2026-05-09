"""Autonomous task runner — executes a markdown task list via claude CLI."""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

TASK_PATTERN = re.compile(r"^- \[([ x])\] (.+?)(?:\s*<!--(.+?)-->\s*)*$")
METADATA_BLOCK = re.compile(r"<!--(.+?)-->")
METADATA_KV = re.compile(r"(\w+):\s*(.+)")


@dataclass
class Task:
    line_number: int
    description: str
    completed: bool
    metadata: dict[str, str] = field(default_factory=dict)
    raw_line: str = ""


@dataclass
class TaskResult:
    task: Task
    success: bool
    output: str = ""
    error: str = ""
    skipped: bool = False


@dataclass
class Config:
    task_file: Path = Path("tasks.md")
    project_dir: Path = Path(".")
    claude_cmd: str = "claude"
    auto_commit: bool = True
    timeout: int = 600
    log_file: Path = Path("task_run.log")
    dry_run: bool = False
    verbose: bool = False


def parse_tasks(path: Path) -> list[Task]:
    tasks = []
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    in_comment = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "<!--" in stripped and "-->" not in stripped:
            in_comment = True
            continue
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        m = TASK_PATTERN.match(stripped)
        if not m:
            continue
        completed = m.group(1) == "x"
        desc_and_meta = m.group(2)
        description = METADATA_BLOCK.sub("", desc_and_meta).strip()
        metadata = {}
        for block in METADATA_BLOCK.finditer(stripped):
            kv = METADATA_KV.match(block.group(1).strip())
            if kv:
                metadata[kv.group(1)] = kv.group(2).strip()
        tasks.append(Task(
            line_number=i,
            description=description,
            completed=completed,
            metadata=metadata,
            raw_line=line,
        ))
    return tasks


def build_prompt(task: Task, config: Config) -> str:
    parts = [
        f"You are working on a project at: {config.project_dir.resolve()}",
        f"\nTask: {task.description}",
    ]
    if "files" in task.metadata:
        parts.append(f"\nRelevant files: {task.metadata['files']}")
    if "context" in task.metadata:
        parts.append(f"\nAdditional context: {task.metadata['context']}")
    parts.append(
        "\nInstructions:"
        "\n- Read CLAUDE.md for project conventions before starting"
        "\n- Implement the task completely with minimal, focused changes"
        "\n- Follow existing code patterns and conventions"
        "\n- Ensure the code works correctly"
    )
    return "\n".join(parts)


def run_claude(prompt: str, config: Config) -> tuple[bool, str, str]:
    cmd = [config.claude_cmd, "-p", "--dangerously-skip-permissions"]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=config.timeout,
            cwd=str(config.project_dir),
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Timeout after {config.timeout}s"
    except FileNotFoundError:
        print(f"Error: '{config.claude_cmd}' not found. Is Claude CLI installed and in PATH?")
        sys.exit(1)


def git_has_changes(config: Config) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True,
        cwd=str(config.project_dir),
        encoding="utf-8",
    )
    return bool(result.stdout.strip())


def git_commit(task: Task, config: Config) -> bool:
    if not git_has_changes(config):
        return True
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(config.project_dir),
        capture_output=True,
    )
    msg = f"task: {task.description[:72]}"
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        capture_output=True, text=True,
        cwd=str(config.project_dir),
        encoding="utf-8",
    )
    return result.returncode == 0


def mark_task_done(path: Path, task: Task) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    old = lines[task.line_number]
    lines[task.line_number] = old.replace("- [ ]", "- [x]", 1)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def log_result(result: TaskResult, log_file: Path) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "OK" if result.success else "FAIL"
    entry = f"[{timestamp}] [{status}] {result.task.description}\n"
    if result.error:
        entry += f"  Error: {result.error[:500]}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


def run_all(config: Config) -> list[TaskResult]:
    if not config.task_file.exists():
        print(f"Error: Task file not found: {config.task_file}")
        sys.exit(1)

    tasks = parse_tasks(config.task_file)
    pending = [t for t in tasks if not t.completed]

    if not pending:
        print("No pending tasks found.")
        return []

    print(f"Found {len(pending)} pending task(s). Starting execution...\n")
    results = []

    for i, task in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] {task.description}")

        if config.dry_run:
            prompt = build_prompt(task, config)
            print(f"  Prompt preview:\n{prompt[:200]}...\n")
            results.append(TaskResult(task=task, success=True, skipped=True))
            continue

        prompt = build_prompt(task, config)
        success, stdout, stderr = run_claude(prompt, config)

        if config.verbose and stdout:
            print(f"  Output: {stdout[:500]}")

        if success:
            print("  Done.")
            if config.auto_commit:
                committed = git_commit(task, config)
                if committed:
                    print("  Committed.")
            mark_task_done(config.task_file, task)
            if config.auto_commit:
                subprocess.run(
                    ["git", "add", str(config.task_file)],
                    cwd=str(config.project_dir), capture_output=True,
                )
                subprocess.run(
                    ["git", "commit", "--amend", "--no-edit"],
                    cwd=str(config.project_dir), capture_output=True,
                )
        else:
            print(f"  Failed: {stderr[:200]}")

        tr = TaskResult(task=task, success=success, output=stdout, error=stderr)
        results.append(tr)
        log_result(tr, config.log_file)

    return results


def print_summary(results: list[TaskResult]) -> None:
    if not results:
        return
    succeeded = sum(1 for r in results if r.success and not r.skipped)
    failed = sum(1 for r in results if not r.success)
    skipped = sum(1 for r in results if r.skipped)

    print(f"\n{'=' * 40}")
    print(f"Task Run Summary")
    print(f"{'=' * 40}")
    print(f"Total:     {len(results)}")
    print(f"Succeeded: {succeeded}")
    print(f"Failed:    {failed}")
    if skipped:
        print(f"Skipped:   {skipped} (dry-run)")
    if failed:
        print(f"\nFailed tasks:")
        for r in results:
            if not r.success:
                print(f"  - {r.task.description}: {r.error[:100]}")


def main():
    parser = argparse.ArgumentParser(description="Autonomous task runner via Claude CLI")
    parser.add_argument("--tasks", type=Path, default=Path("tasks.md"), help="Task file path")
    parser.add_argument("--project-dir", type=Path, default=Path("."), help="Project directory")
    parser.add_argument("--no-commit", action="store_true", help="Disable auto-commit")
    parser.add_argument("--dry-run", action="store_true", help="Parse and show prompts only")
    parser.add_argument("--timeout", type=int, default=600, help="Per-task timeout in seconds")
    parser.add_argument("--log", type=Path, default=Path("task_run.log"), help="Log file path")
    parser.add_argument("--verbose", action="store_true", help="Print Claude output")
    args = parser.parse_args()

    config = Config(
        task_file=args.tasks,
        project_dir=args.project_dir,
        auto_commit=not args.no_commit,
        timeout=args.timeout,
        log_file=args.log,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    results = run_all(config)
    print_summary(results)


if __name__ == "__main__":
    main()
