"""Markdown checklist task parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .schema import TaskSpec

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


def _split_metadata_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]


def task_to_spec(task: Task) -> TaskSpec:
    metadata = task.metadata
    return TaskSpec(
        id=metadata.get("id", f"task-{task.line_number + 1}"),
        description=task.description,
        status="completed" if task.completed else "pending",
        files=_split_metadata_list(metadata.get("files", "")),
        context=metadata.get("context", ""),
        depends_on=_split_metadata_list(metadata.get("depends_on", "")),
        acceptance=_split_metadata_list(metadata.get("acceptance", "")),
        risk=metadata.get("risk", ""),
        owner_role=metadata.get("owner_role", "engineer"),
        validation_commands=_split_metadata_list(metadata.get("validation_commands", "")),
        run_id=metadata.get("run_id", ""),
    )


def tasks_to_specs(tasks: list[Task]) -> list[TaskSpec]:
    return [task_to_spec(task) for task in tasks]


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
        match = TASK_PATTERN.match(stripped)
        if not match:
            continue
        completed = match.group(1) == "x"
        desc_and_meta = match.group(2)
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
