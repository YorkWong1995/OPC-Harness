# Review Workflow Pack

## Manifest

| 字段 | 值 |
| --- | --- |
| `id` | `review` |
| `kind` | `claude_skill` |
| `owner_roles` | `QA`, `Architect` |
| `inputs` | pending diff、PR、任务结果、指定文件、任务目标、验收标准 |
| `outputs` | blocking 问题、non-blocking 建议、风险判断、pass/needs-work/needs-info 结论 |
| `permissions` | 默认只读；不写代码、不执行修复、不发布 |
| `acceptance` | 问题分类清晰，blocking 与 non-blocking 区分明确，每条结论有证据 |
| `trace` | skill 模式默认不写 runtime trace；若转 runtime workflow，由目标 pack 记录 trace |

## 适用场景

- PR、pending diff、任务结果或指定文件需要独立评审。
- 需要判断是否存在 blocking 风险，而不是直接修复。
- 需要 Architect/QA 视角检查范围、兼容性、安全、测试和发布风险。

## 不适用场景

- 需要直接修改代码、补测试或修复缺陷。
- 需要执行发布、部署、上传或回滚。
- 需要完整 QA 验收报告时，应使用 `/acceptance-check` 或 runtime QA 阶段。

## Skill 与 Runtime Workflow 边界

- 默认使用 `/review` skill 执行只读评审。
- 若评审发现需要写代码或补测试，转 bugfix pack 或 docs-update pack。
- 若评审对象是发布前风险，转 release-check pack。
- 若需要 run_id、artifact、QA 回退和复盘记录，应转对应 `opc_runtime_workflow` pack。

## 角色边界

| 角色 | 责任 | 禁止事项 |
| --- | --- | --- |
| QA | 检查验收标准、测试证据和回归风险 | 不直接修复代码，不把缺少证据判为通过 |
| Architect | 检查架构边界、兼容性、安全和长期风险 | 不扩大范围为新架构设计，除非用户明确要求 |

## 输入要求

- `review_target`：PR、diff、文件路径或任务结果。
- `task_goal`：本次变更要达成的目标。
- `acceptance_criteria`：可验证标准或任务完成标准。
- `evidence`：已运行测试、命令输出、截图或文档引用。

## 输出要求

- `blocking_issues`：必须修复的问题，包含影响、证据和建议修正方向。
- `non_blocking_suggestions`：可延后建议，必须说明为什么不阻塞。
- `risk_assessment`：正确性、安全、兼容性、测试、发布维度判断。
- `conclusion`：`pass` / `needs-work` / `needs-info`。

## 权限边界

- 默认只读：读取 diff、文件、PR 描述、任务和验证证据。
- 不写入文件，不运行修复命令，不提交、不推送、不发布。
- 如需写代码、补测试或更新文档，必须转交 bugfix 或 docs-update pack。

## 验收标准

- review pack 明确默认只读。
- blocking 与 non-blocking 分类规则清楚。
- 每条问题或建议都有文件路径、行号、命令或 diff 证据。
- 若需要写代码，结论必须指向 bugfix 或 docs-update pack。

## Trace / Artifact 要求

- skill 模式：不创建 runtime trace，仅输出评审文本。
- 转 runtime workflow：由 bugfix、docs-update 或 release-check pack 记录 run_events、trace 和 artifacts。

## 转交规则

- 存在可修复缺陷：转 bugfix pack。
- 只需文档更新：转 docs-update pack。
- 发布前检查：转 release-check pack。
- 信息不足：输出 `needs-info` 并列出缺失输入。
