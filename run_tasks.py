"""Autonomous task runner — executes a markdown task list via claude CLI."""

import argparse
import os
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


def _resolve_claude_cmd(cmd: str) -> str:
    if Path(cmd).is_file():
        return cmd
    import shutil
    found = shutil.which(cmd)
    if found:
        return found
    app_data = Path(os.environ.get("APPDATA", ""))
    for candidate in [
        app_data / "npm" / "claude.cmd",
        app_data / "npm" / "claude",
    ]:
        if candidate.exists():
            return str(candidate)
    return cmd


def run_claude(prompt: str, config: Config) -> tuple[bool, str, str]:
    cmd = [_resolve_claude_cmd(config.claude_cmd), "-p", "--dangerously-skip-permissions"]
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

        if "decision" in task.metadata:
            print(f"  Skipped (needs decision): {task.metadata['decision']}")
            results.append(TaskResult(task=task, success=False, skipped=True))
            continue

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
    failed = sum(1 for r in results if not r.success and not r.skipped)
    skipped_dry = sum(1 for r in results if r.skipped and r.success)
    skipped_decision = sum(1 for r in results if r.skipped and not r.success)

    print(f"\n{'=' * 40}")
    print(f"Task Run Summary")
    print(f"{'=' * 40}")
    print(f"Total:     {len(results)}")
    print(f"Succeeded: {succeeded}")
    print(f"Failed:    {failed}")
    if skipped_dry:
        print(f"Skipped:   {skipped_dry} (dry-run)")
    if skipped_decision:
        print(f"Deferred:  {skipped_decision} (needs decision)")
    if failed:
        print(f"\nFailed tasks:")
        for r in results:
            if not r.success and not r.skipped:
                print(f"  - {r.task.description}: {r.error[:100]}")


def plan_tasks(goal: str, config: Config) -> None:
    prompt = f"""You are a technical project planner analyzing a codebase at: {config.project_dir.resolve()}

Goal: {goal}

Instructions:
1. Read CLAUDE.md and explore the project structure to understand the codebase
2. Break down the goal into concrete, independently executable tasks
3. Order tasks by dependency (tasks that others depend on come first)
4. Each task should be completable in a single session (< 10 minutes)

Output ONLY a markdown task list in this exact format (no other text):

# Tasks

- [ ] First task description <!-- files: relevant/file.py -->
- [ ] Second task description <!-- context: additional info -->
- [ ] Third task description

Rules for task decomposition:
- Each task should be atomic — one clear change or addition
- Include <!-- files: ... --> when specific files are involved
- Include <!-- context: ... --> for non-obvious constraints
- 5-15 tasks is typical; fewer for simple goals, more for complex ones
- Tasks should be ordered so each can be executed without depending on later ones
"""
    print(f"Planning tasks for: {goal}\n")
    success, stdout, stderr = run_claude(prompt, config)
    if not success:
        print(f"Error during planning: {stderr[:300]}")
        sys.exit(1)

    task_lines = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") or TASK_PATTERN.match(stripped):
            task_lines.append(line)

    if not task_lines:
        print("Error: Claude did not produce a valid task list.")
        print(f"Raw output:\n{stdout[:500]}")
        sys.exit(1)

    output = "\n".join(task_lines) + "\n"
    config.task_file.write_text(output, encoding="utf-8")
    task_count = sum(1 for l in task_lines if l.strip().startswith("- [ ]"))
    print(f"Generated {task_count} tasks → {config.task_file}\n")
    print(output)


def main():
    parser = argparse.ArgumentParser(description="Autonomous task runner via Claude CLI")
    parser.add_argument("--plan", type=str, metavar="GOAL", help="Auto-decompose a goal into tasks")
    parser.add_argument("--tasks", type=Path, default=Path("tasks.md"), help="Task file path")
    parser.add_argument("--project-dir", type=Path, default=Path("."), help="Project directory")
    parser.add_argument("--no-commit", action="store_true", help="Disable auto-commit")
    parser.add_argument("--dry-run", action="store_true", help="Parse and show prompts only")
    parser.add_argument("--timeout", type=int, default=600, help="Per-task timeout in seconds")
    parser.add_argument("--log", type=Path, default=Path("task_run.log"), help="Log file path")
    parser.add_argument("--verbose", action="store_true", help="Print Claude output")
    parser.add_argument("--plan-and-run", type=str, metavar="GOAL",
                        help="Plan tasks then immediately execute them")
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

    if args.plan:
        plan_tasks(args.plan, config)
        return

    if args.plan_and_run:
        plan_tasks(args.plan_and_run, config)
        print("--- Starting execution ---\n")

    results = run_all(config)
    print_summary(results)


if __name__ == "__main__":
    main()
