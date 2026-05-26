#!/usr/bin/env python3
"""Run the autonomous task runner through the legacy root entry point."""

from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "run_tasks.py"), run_name="__main__")
