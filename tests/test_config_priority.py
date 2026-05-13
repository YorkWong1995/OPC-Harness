"""测试配置优先级链。"""

import os
from pathlib import Path

from opc.config import load_project_config


def test_default_config_without_toml(tmp_path: Path):
    config = load_project_config(tmp_path)
    assert config.workflow.max_rounds == 12
    assert config.cost.workflow_token_limit == 200_000


def test_toml_overrides_defaults(tmp_path: Path):
    (tmp_path / "opc.toml").write_text(
        "[workflow]\nmax_rounds = 5\n[cost]\nworkflow_token_limit = 100000\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.workflow.max_rounds == 5
    assert config.cost.workflow_token_limit == 100_000


def test_env_overrides_toml(tmp_path: Path, monkeypatch):
    (tmp_path / "opc.toml").write_text("[workflow]\nmax_rounds = 5\n", encoding="utf-8")
    monkeypatch.setenv("OPC_MAX_ROUNDS", "20")

    config = load_project_config(tmp_path)
    assert config.workflow.max_rounds == 20


def test_cli_overrides_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPC_MAX_ROUNDS", "20")

    config = load_project_config(tmp_path, cli_overrides={"max_rounds": 99})
    assert config.workflow.max_rounds == 99


def test_runtime_overrides_cli(tmp_path: Path):
    config = load_project_config(
        tmp_path,
        cli_overrides={"max_rounds": 99},
        runtime_overrides={"max_rounds": 3},
    )
    assert config.workflow.max_rounds == 3
