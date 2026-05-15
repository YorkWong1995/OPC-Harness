"""测试 P0.3 成本硬限制：超过阈值应抛出 _StopWorkflow。"""

import pytest

from opc.workflow import HarnessWorkflow, _StopWorkflow


def test_role_token_hard_limit_triggers_stop(tmp_path):
    wf = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)
    wf.opc_config.cost.role_token_hard_limit = 100
    wf.opc_config.cost.workflow_token_hard_limit = 0  # 关闭工作流维度
    wf.opc_config.cost.enforce_hard_limit = True

    with pytest.raises(_StopWorkflow):
        wf._observe_cost_limits("已定义", stage_tokens=200, stage_api_calls=1)


def test_workflow_token_hard_limit_triggers_stop(tmp_path):
    wf = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)
    wf.workflow_state.stage_logs["已定义"] = {"input_tokens": 80, "output_tokens": 70}
    wf.opc_config.cost.workflow_token_hard_limit = 100
    wf.opc_config.cost.role_token_hard_limit = 0
    wf.opc_config.cost.enforce_hard_limit = True

    with pytest.raises(_StopWorkflow):
        wf._observe_cost_limits("实现中", stage_tokens=10, stage_api_calls=1)


def test_hard_limit_disabled_only_warns(tmp_path):
    wf = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)
    wf.opc_config.cost.role_token_hard_limit = 100
    wf.opc_config.cost.enforce_hard_limit = False

    # 不抛出
    wf._observe_cost_limits("已定义", stage_tokens=200, stage_api_calls=1)


def test_hard_limit_zero_means_disabled(tmp_path):
    wf = HarnessWorkflow(task="t", project_dir=tmp_path, auto_confirm=True)
    wf.opc_config.cost.role_token_hard_limit = 0  # 0 = disabled
    wf.opc_config.cost.workflow_token_hard_limit = 0
    wf.opc_config.cost.enforce_hard_limit = True

    # 即使 stage_tokens 很大也不应中止
    wf._observe_cost_limits("已定义", stage_tokens=1_000_000, stage_api_calls=1)
