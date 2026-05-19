"""测试基础安装可运行的默认 Embedding 配置。"""

from __future__ import annotations

import importlib

from opc.config import load_project_config


def test_default_embedding_model_is_minilm(monkeypatch):
    monkeypatch.delenv("OPC_EMBEDDING_MODEL", raising=False)
    import opc.knowledge.embedder as embedder

    module = importlib.reload(embedder)

    assert module.EMBEDDING_MODEL_NAME == "ONNXMiniLM_L6_V2"
    assert module.EMBEDDING_DIMENSION == 384


def test_embedding_model_env_override(monkeypatch):
    monkeypatch.setenv("OPC_EMBEDDING_MODEL", "bge-small-zh")
    import opc.knowledge.embedder as embedder

    module = importlib.reload(embedder)

    assert module.EMBEDDING_MODEL_NAME == "BAAI/bge-small-zh-v1.5"
    assert module.EMBEDDING_DIMENSION == 512


def test_config_exposes_embedding_model(tmp_path, monkeypatch):
    monkeypatch.delenv("OPC_EMBEDDING_MODEL", raising=False)

    config = load_project_config(tmp_path)

    assert config.memory.embedding_model == "minilm"


def test_config_embedding_model_priority(tmp_path, monkeypatch):
    (tmp_path / "opc.toml").write_text('[memory]\nembedding_model = "minilm"\n', encoding="utf-8")
    monkeypatch.setenv("OPC_EMBEDDING_MODEL", "bge-m3")

    config = load_project_config(tmp_path, runtime_overrides={"embedding_model": "custom-model"})

    assert config.memory.embedding_model == "custom-model"
