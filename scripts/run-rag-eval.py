#!/usr/bin/env python
"""Run lightweight OPC RAG golden eval without LLM calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from opc.knowledge.rag_eval import run_rag_eval


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight OPC RAG eval")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--dataset", type=Path, default=PROJECT_ROOT / "tests" / "fixtures" / "rag_eval_dataset.json")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report path")
    args = parser.parse_args()

    report = run_rag_eval(args.project_root.resolve(), args.dataset.resolve(), top_k=args.top_k)
    summary = {key: report[key] for key in ["top_k", "queries", "corpus_chunks", "hit_rate", "mrr", "ndcg", "hits", "misses"]}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["output"] = str(args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
