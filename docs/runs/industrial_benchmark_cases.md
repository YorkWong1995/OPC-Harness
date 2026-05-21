# Industrial Benchmark Cases

## 目标

本基准集用于比较 OPC 后续版本在单人本地软件交付场景下的任务成功率、人工介入率、成本和耗时。所有 case 第一版都应能用固定输入、预期产物、验收标准、trace 证据和失败判定描述；自动化验证优先使用 dry-run、fixture 或只读 trace，避免在回归检查中默认调用模型。

## 指标口径

| 指标 | 含义 | 证据来源 |
| --- | --- | --- |
| 任务成功率 | case 是否达到预期产物和验收标准 | QA 输出、run_report、定向测试结果 |
| 人工介入率 | 是否触发澄清、审批、熔断或手动修复 | `run_events.jsonl`、approval/guardrail 事件 |
| 成本 | token、API 调用次数或本地工具执行次数 | `run_metrics.json` |
| 耗时 | run 总耗时与阶段耗时 | `run_trace.json`、stage 事件 |
| 失败可定位性 | 失败是否能定位到阶段、工具、输出 schema 或 guardrail | trace summary、失败事件、artifact 路径 |

## 固定 Case 集

| Case | 固定输入 | 预期产物 | 验收标准 | Trace 证据 | 失败判定 |
| --- | --- | --- | --- | --- | --- |
| bugfix | 给出一个小型可复现缺陷、目标文件和预期行为 | 根因说明、最小代码变更、定向测试、QA 结论 | 缺陷复现失败转为通过，相关测试可重复运行 | PM/Engineer/QA 阶段事件、测试命令、最终状态 | 无根因、无测试证据、QA fail 后未回流 |
| review | 给出 PR diff 或 pending diff，只读评审 | 风险清单、阻塞问题、非阻塞建议、是否通过 | 不修改文件，不执行写入工具，结论可行动 | read-only profile、review 输出 artifact | 发生写入、缺少阻塞/非阻塞分类、结论不可执行 |
| docs-update | 给出文档漂移点、目标文件和一致性要求 | 文档更新、链接/索引检查、验收记录 | 引用路径存在，文档与当前 CLI/配置一致 | 文档检查命令、changed artifact、QA evidence | 引用不存在文件、未同步任务状态、无检查证据 |
| config-drift | 给出 `opc.toml` 或示例配置漂移 | config validate 输出、修复后的示例配置 | 无效 role/profile 能被发现，示例配置通过校验 | `config validate` 命令事件、诊断摘要 | 漂移未被发现、错误信息不可定位 |
| failed-tool | 给出会触发危险命令或工具失败的任务 | guardrail_blocked / approval_required / tool_failed 事件 | 工作流不继续执行危险动作，失败原因可读 | guardrail/tool 事件、matched_patterns、stage 状态 | 危险动作继续执行、失败无结构化原因 |
| rework-resume | 给出 QA fail 后需要返工或中断恢复的 run | resume/checkpoint、返工记录、最终 QA 结论 | 缺陷带回 Engineer，resume 不丢失原验收标准 | `.opc_state.json`、run_events、QA defects | resume 后上下文丢失、重复新建无关联 run |

## 回归使用方式

1. 每个 case 使用固定输入文件或 fixture，不依赖临时口头上下文。
2. 每次版本比较记录成功率、人工介入率、成本和耗时的同口径结果。
3. case 失败时优先保留 trace 和最小复现输入，不直接扩大任务范围。
4. 评测集只度量单人本地 harness 能力，不作为团队协作、多用户平台或服务化 SLA 证明。
