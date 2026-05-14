"""Markdown checklist task parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
