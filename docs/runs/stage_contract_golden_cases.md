# Stage Contract Golden Cases

## 目标

本 golden case 集用于验证阶段契约没有回退：每类任务都有固定输入、预期阶段输出、预期 transition、预期失败分支和失败判定。第一版只验证契约层和 fixture，不调用模型。

| Case | 固定输入 | 预期阶段输出 | 预期 transition | 预期失败分支 | 失败判定 |
| --- | --- | --- | --- | --- | --- |
| bugfix | 可复现缺陷、目标文件、预期行为 | PMOutput → EngineerOutput → QAOutput(pass) | pm: 已定义；engineer: 实现中；qa: 已通过 | qa fail → 已退回 | 缺少测试证据或 QA fail 后不回退 |
| review | pending diff，只读评审目标 | QAOutput(pass/fail) 或 review artifact | qa pass → 已通过；qa fail → 已退回 | 已退回 | 发生写入或无阻塞/非阻塞分类 |
| docs-update | 文档漂移点和目标文档 | PMOutput → EngineerOutput → QAOutput(pass) | docs 修复后 qa pass → 已通过 | 已退回 | 链接漂移仍存在或无检查证据 |
| config-drift | 无效 role/profile 配置 | EngineerOutput(test_result=config validate) → QAOutput | validate pass → 待验收/已通过 | 已退回 | 无效配置未被发现或诊断不可读 |
| failed-tool | 危险命令或工具失败输入 | StageResult(status=failed) + validation_failed/guardrail event | error/deny 不进入下一阶段 | 已退回 | 危险动作继续执行或无结构化原因 |
| rework-resume | QA fail 后 resume 的固定状态 | QAOutput(fail) → EngineerOutput(rework) → QAOutput(pass) | fail → 已退回；rework pass → 实现中；final qa → 已通过 | 已退回 | resume 丢失 defects、acceptance 或 artifact |

## Fixture 约束

- 每个 case 的角色输出必须符合对应 `output_schema`，除非该 case 明确测试 validation failure。
- 每个失败 case 必须声明 `failure_branch`，第一版统一验证为 `已退回`。
- 每个 case 必须能通过只读测试验证，不依赖临时口头上下文或模型调用。
