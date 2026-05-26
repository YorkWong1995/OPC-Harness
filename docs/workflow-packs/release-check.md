# Release-check Workflow Pack

## Manifest

| 字段 | 值 |
| --- | --- |
| `id` | `release-check` |
| `kind` | `claude_skill` |
| `owner_roles` | `Ops`, `QA` |
| `inputs` | 发布对象、实现结果、QA 证据、环境信息、运行验证方式、回滚条件 |
| `outputs` | 发布前检查项、监控关注点、人工确认节点、ready/needs-info/not-ready 结论 |
| `permissions` | 默认只读；不执行真实发布、部署、push、上传或回滚 |
| `acceptance` | 明确不执行发布，检查项完整，回滚条件清楚，缺信息时不输出 ready |
| `trace` | skill 模式默认不写 runtime trace；若接入发布流程，必须记录 approval_required 和 approval_decision |

## 适用场景

- 变更准备发布前，需要检查验证证据、环境、监控和回滚条件。
- 发布对象涉及脚本、配置、文档资产、CLI 能力或外部系统影响。
- 需要整理人工确认节点，而不是执行真实发布动作。

## 不适用场景

- 执行真实部署、上传、推送、迁移、删除或回滚。
- 替代 QA 验收或修复发布前发现的缺陷。
- 缺少发布对象、环境或 QA 证据时强行判断可发布。

## Skill 与 Runtime Workflow 边界

- 默认使用 `/release-check` skill 输出只读发布建议。
- 若需要修复发布阻塞问题，转 bugfix 或 docs-update pack。
- 若要执行真实发布，必须由人工确认后使用单独发布命令或外部流程，不由本 pack 自动执行。
- 若未来接入 runtime 发布流程，必须把审批、回滚和熔断写入 trace。

## 角色边界

| 角色 | 责任 | 禁止事项 |
| --- | --- | --- |
| Ops | 检查环境、运行验证、监控、回滚和人工确认节点 | 不执行真实发布或修改共享基础设施 |
| QA | 确认验收结果、测试证据和发布前阻塞项 | 不绕过失败测试或缺失证据 |

## 输入要求

- `release_target`：发布对象、版本、范围和目标环境。
- `implementation_result`：实现摘要、变更文件和相关 artifacts。
- `qa_evidence`：验收结论、验证命令、测试结果和未覆盖项。
- `runtime_validation`：发布后验证路径、命令、接口、页面或日志。
- `rollback_plan`：回滚触发条件、入口、负责人和证据保留方式。

## 输出要求

- `pre_release_checks`：发布前检查项和状态。
- `runtime_validation`：发布后如何验证成功。
- `monitoring_focus`：发布后观察指标、日志或告警。
- `rollback_conditions`：触发回滚的信号和动作。
- `human_approval`：需要人工确认的节点。
- `conclusion`：`ready` / `needs-info` / `not-ready`。

## 权限边界

- 只读检查实现结果、QA 证据、文档、配置说明和环境信息。
- 不运行发布命令，不 push，不上传，不部署，不回滚。
- 涉及外部系统或共享基础设施时必须标记人工确认。

## 验收标准

- Pack 明确不执行真实发布，只输出检查结论和回滚条件。
- 输出包含发布前检查项、运行验证方式、监控关注点和人工确认节点。
- 缺少 QA 证据、环境信息或回滚条件时结论为 `needs-info`。
- 存在失败测试、阻塞缺陷或未批准危险操作时结论为 `not-ready`。

## Trace / Artifact 要求

- skill 模式：不创建 runtime trace，仅输出发布检查文本。
- 若转 runtime 发布流程：必须记录 approval_required、approval_decision、rollback_decision 和 circuit_breaker_open。
- 发布检查文本可作为 release artifact 保存，但不代表发布已执行。

## 转交规则

- 发现缺陷：转 bugfix pack。
- 发现文档或索引缺失：转 docs-update pack。
- 信息不足：输出 `needs-info` 并列出缺失项。
- 用户确认执行真实发布：离开本 pack，进入单独发布流程或命令。
