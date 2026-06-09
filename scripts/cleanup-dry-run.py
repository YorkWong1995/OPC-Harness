#!/usr/bin/env python
"""Dry-run local cleanup candidates for OPC artifacts and indexes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from opc.knowledge.index_paths import inspect_indexes
from opc.run_store import find_run_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="List OPC cleanup candidates; never deletes files")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--include", choices=["artifacts", "index", "all"], default="all")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve()
    candidates = []
    if args.include in {"artifacts", "all"}:
        candidates.extend({"type": "artifacts", "path": str(path), "reason": "run artifact directory"} for path in find_run_artifacts(root))
    if args.include in {"index", "all"}:
        candidates.extend({"type": "index", "path": item["index_root"], "reason": "knowledge index cache"} for item in inspect_indexes().get("indexes", []))
    report = {"mode": "dry-run", "root": str(root), "candidates": candidates, "deleted": []}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
