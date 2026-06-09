#!/usr/bin/env python
"""Create a local OPC release-check report without publishing or deleting anything."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _git_commit(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _exists(path: Path, blocking: bool = True) -> dict[str, str | bool]:
    return {
        "name": path.as_posix(),
        "status": "pass" if path.exists() else "fail" if blocking else "needs-env",
        "command": "path exists",
        "blocking": blocking,
        "skip_reason": "" if path.exists() else "required local file is missing" if blocking else "requires target environment or CI evidence",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create local release gate report")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--version", default="local")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    checks = [
        _exists(project_root / ".github" / "workflows" / "ci.yml"),
        _exists(project_root / ".github" / "workflows" / "docker-publish.yml", blocking=False),
        _exists(project_root / "tests" / "test_cli_smoke.py"),
        _exists(project_root / "tests" / "test_project_kb_quality.py"),
        _exists(project_root / "scripts" / "run-rag-eval.py"),
        _exists(project_root / "docs" / "DOCS_STRUCTURE.md"),
        _exists(project_root / "docs" / "workflow-packs" / "release-check.md"),
    ]
    blocking = [check for check in checks if check["blocking"] and check["status"] != "pass"]
    needs_env = [check for check in checks if check["status"] == "needs-env"]
    report = {
        "schema": "opc.release_report.v1",
        "version": args.version,
        "commit": _git_commit(project_root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "blocking_items": blocking,
        "supplemental_validation": needs_env,
        "recommendation": "not-ready" if blocking else "needs-env" if needs_env else "ready",
        "notes": "Local script is read-only except optional report output; CI, Docker, real Qt, security scanning, and full coverage evidence may require target environment.",
    }
    output = args.output or (project_root / "docs" / "runs" / "release_report.local.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "recommendation": report["recommendation"], "blocking": len(blocking), "needs_env": len(needs_env)}, ensure_ascii=False, indent=2))
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
