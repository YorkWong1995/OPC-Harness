"""Smoke tests for documented quickstart examples."""

import subprocess
import sys
from pathlib import Path


def test_quickstart_minimal_dry_run():
    script = Path("examples/quickstart_minimal.py")

    result = subprocess.run(
        [sys.executable, str(script), "--task", "smoke task", "--project", "quickstart-test"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode == 0
    assert "-m opc.cli run smoke task --project quickstart-test" in result.stdout
    assert "Dry run only" in result.stdout
