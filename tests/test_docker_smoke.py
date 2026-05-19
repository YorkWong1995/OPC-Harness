import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opc import __version__


def test_docker_assets_define_opc_entrypoint():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")

    assert "FROM python:3.11-slim" in dockerfile
    assert 'ENTRYPOINT ["opc"]' in dockerfile
    assert 'CMD ["--help"]' in dockerfile
    assert "workspace" in dockerignore
    assert ".env" in dockerignore


def test_opc_version_command():
    result = subprocess.run(
        [sys.executable, "-m", "opc.cli", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode == 0
    assert f"opc {__version__}" in result.stdout


def test_opc_run_basic_parser_smoke(tmp_path):
    from opc.cli import main

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    workflow = MagicMock()
    workflow.run = AsyncMock()

    with (
        patch("sys.argv", ["opc", "run", "smoke task", "--project-dir", str(project_dir), "--auto-confirm"]),
        patch("opc.cli.HarnessWorkflow", return_value=workflow) as workflow_cls,
    ):
        main()

    workflow_cls.assert_called_once()
    assert workflow_cls.call_args.kwargs["task"] == "smoke task"
    assert workflow_cls.call_args.kwargs["project_dir"] == project_dir
    assert workflow_cls.call_args.kwargs["auto_confirm"] is True
    workflow.run.assert_called_once()


def test_docker_image_smoke_when_image_is_available():
    image = os.environ.get("OPC_DOCKER_SMOKE_IMAGE")
    if not image:
        pytest.skip("Set OPC_DOCKER_SMOKE_IMAGE to run container smoke checks")
    if not shutil.which("docker"):
        pytest.skip("docker CLI is not available")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,255}", image):
        pytest.fail("OPC_DOCKER_SMOKE_IMAGE is not a valid Docker image reference")

    version = subprocess.run(
        ["docker", "run", "--rm", image, "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert version.returncode == 0, version.stderr
    assert "opc " in version.stdout

    help_result = subprocess.run(
        ["docker", "run", "--rm", image, "run", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "任务描述" in help_result.stdout
