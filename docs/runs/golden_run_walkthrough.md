# Golden Run Walkthrough

## 目标

本 walkthrough 用于验证 OPC 新用户从安装、运行、查看 trace 到验收的最小闭环。样例默认使用 dry-run 或已有 artifacts 检查方式，避免在文档验证中调用模型。

## 样例 1：Quickstart 最小工作流

### 命令

```bash
python examples/quickstart_minimal.py
python examples/quickstart_minimal.py --execute --auto-confirm --project demo-readme
```

### 输入任务

为示例项目补充一个最小 README 变更，并给出验收记录。

### 预期产物

- `workspace/demo-readme/artifacts/run_report.md`
- `workspace/demo-readme/artifacts/run_trace.json`
- `workspace/demo-readme/artifacts/run_metrics.json`

### Trace 查看

```bash
opc runs list --project-dir workspace/demo-readme
opc trace summary --artifacts-dir workspace/demo-readme/artifacts
opc trace show --artifacts-dir workspace/demo-readme/artifacts --limit 20
```

### 验收标准

- PM、Engineer、QA 产物存在或在 run report 中可追踪。
- `run_trace.json` 可被 `opc trace summary` 读取。
- QA 结论明确为 pass/fail，并给出 evidence。

### 失败排查

- 如果缺少 `ANTHROPIC_API_KEY`，先运行 `opc doctor`。
- 如果 artifacts 不存在，确认是否只执行了 dry-run。
- 如果 trace 缺字段，使用 `opc trace summary` 检查兼容读取结果。

## 样例 2：配置漂移检查

### 命令

```bash
opc init --project-dir workspace/demo-config
opc config validate --project-dir workspace/demo-config
opc doctor --project-dir workspace/demo-config
```

### 输入任务

验证新项目配置能被初始化、校验和诊断。

### 预期产物

- `workspace/demo-config/opc.toml`
- doctor 输出包含 API key、opc.toml、workspace、index root、commands 状态。

### Trace 查看

该样例不创建 run trace；它验证运行前诊断入口。若后续运行 workflow，可使用：

```bash
opc runs list --project-dir workspace/demo-config
```

### 验收标准

- `opc config validate` 返回成功。
- `opc doctor` 不因缺少 opc.toml 或无效 role/profile 失败。

### 失败排查

- 如果 `opc.toml` 已存在且内容不符合预期，使用 `opc config validate` 查看具体字段。
- 如果 profile 不存在，检查 `[profile.<name>]` 是否声明。

## 样例 3：Trace 只读复盘

### 命令

```bash
opc runs list
opc trace summary --artifacts-dir workspace/demo-readme/artifacts
opc trace show --artifacts-dir workspace/demo-readme/artifacts --limit 50
```

### 输入任务

从已有 artifacts 复盘单次 run 的状态、耗时、失败原因和事件链。

### 预期产物

不新增产物；只读命令从 `run_events.jsonl`、`run_trace.json`、`run_metrics.json` 重建摘要。

### 验收标准

- `runs list` 能列出 run_id、最终状态、耗时、失败原因和 artifacts 路径。
- `trace summary` 能显示 schema version、event count、tool calls、duration。
- `trace show` 不重新调用模型或工具。

### 失败排查

- 如果 `run_trace.json` 缺少 `trace_schema_version`，按旧版 schema 0 读取。
- 如果没有 `run_metrics.json`，摘要仍应显示事件数量与 run_id。
