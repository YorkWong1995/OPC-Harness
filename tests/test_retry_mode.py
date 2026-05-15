"""测试 P0.4 API 重试间隔的 interactive/batch 模式。"""

import os
from unittest.mock import patch

import anthropic
import pytest

from opc.agent import Agent, RETRY_BASE_DELAYS, RETRY_MAX_ATTEMPTS


def test_default_mode_is_interactive(tmp_path):
    agent = Agent(role="t", system_prompt="t", project_dir=tmp_path)
    assert agent.retry_mode == "interactive"
    assert agent.retry_base_delay == RETRY_BASE_DELAYS["interactive"]


def test_explicit_batch_mode(tmp_path):
    agent = Agent(role="t", system_prompt="t", project_dir=tmp_path, retry_mode="batch")
    assert agent.retry_mode == "batch"
    assert agent.retry_base_delay == RETRY_BASE_DELAYS["batch"]


def test_invalid_mode_falls_back_to_interactive(tmp_path):
    agent = Agent(role="t", system_prompt="t", project_dir=tmp_path, retry_mode="weird")
    assert agent.retry_mode == "interactive"


def test_env_override_mode(tmp_path):
    with patch.dict(os.environ, {"OPC_RETRY_MODE": "batch"}):
        agent = Agent(role="t", system_prompt="t", project_dir=tmp_path)
        assert agent.retry_mode == "batch"


def test_retry_uses_short_delay_in_interactive(tmp_path):
    """在 interactive 模式下，重试间隔应该 <30s（基础 10s）。"""
    agent = Agent(role="t", system_prompt="t", project_dir=tmp_path)
    assert agent.retry_base_delay < 30

    sleep_calls: list[float] = []

    error = anthropic.APITimeoutError(request=None)

    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        raise error

    with patch.object(agent.client.messages, "create", side_effect=fake_create), \
         patch("opc.agent.time.sleep", side_effect=lambda d: sleep_calls.append(d)):
        with pytest.raises(anthropic.APITimeoutError):
            agent._call_with_retry()

    assert call_count["n"] == RETRY_MAX_ATTEMPTS
    assert sleep_calls, "应触发至少一次 sleep"
    for delay in sleep_calls:
        assert delay < 60  # 交互模式重试应在分钟级以下
