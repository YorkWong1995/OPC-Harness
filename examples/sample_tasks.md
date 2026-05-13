# OPC 样例任务

以下样例任务用于验证 OPC 核心能力，覆盖典型软件交付场景。

## 1. Bug 修复

```bash
opc run "修复 config.py 中 load_workflow_config 在 opc.toml 不存在时返回空 roles 的问题" \
  --project demo-bugfix --auto-confirm
```

**验证点：** PM 定义问题 → Engineer 定位并修复 → QA 验证修复有效

## 2. 功能新增

```bash
opc run "为项目添加一个 health check 端点，返回版本号和运行状态" \
  --project demo-feature --auto-confirm
```

**验证点：** PM 定义需求和验收标准 → Engineer 实现 → QA 验证功能正确

## 3. 返工恢复

```bash
# 第一次运行（模拟 QA 失败）
opc run "实现用户注册功能，要求密码强度校验" --project demo-rework --auto-confirm

# 如果 QA 退回，观察自动返工流程
# 如果中断，使用 resume 恢复
opc resume --project demo-rework
```

**验证点：** QA 退回后 Engineer 收到 defects 并重新实现 → 再次验收

## 4. 实现一个轻量级工具

```bash
opc run "为 OPC 添加一个 'opc version' 子命令，输出当前版本号" \
  --project demo-tool --auto-confirm
```

**验证点：** 完整 PM → Engineer → QA 闭环，产物为可运行的 CLI 子命令

## 运行样例后检查

每个样例运行后，检查 `workspace/<project>/artifacts/` 目录：

- `run_trace.json` — 完整事件链
- `run_metrics.json` — token 用量和质量指标
- `tool_audit.jsonl` — 工具调用审计
- `.opc_state.json` — 可恢复的工作流状态
