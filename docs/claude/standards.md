# 文档产出规范

项目中的核心文档应尽量标准化。

## PRD 应至少包含

- 背景
- 目标
- 用户场景
- 功能范围
- 非目标
- 验收标准

> 参考样例：[docs/plan/vision.md](../plan/vision.md)、[docs/plan/success.md](../plan/success.md)

## 架构文档应至少包含

- 目标问题
- 模块拆分
- 关键数据流
- 接口定义
- 技术约束
- 风险与取舍

> 参考样例：[docs/plan/architecture.md](../plan/architecture.md)、[docs/knowledge-retrieval-design.md](../knowledge-retrieval-design.md)

## 任务清单应至少包含

- 任务名称
- 责任角色
- 输入
- 输出
- 依赖关系
- 完成标准

## 角色 I/O artifact 应至少包含

当任务按 OPC 流程执行时，每个参与角色必须维护独立 artifact，使用以下通用 schema：

```yaml
schema: opc.role_io.v1
task_id: ""
role: ""
phase: ""
status: pending | in_progress | done | blocked
input:
  user_request: ""
  upstream_artifacts: []
  constraints: []
  read_before_start: []
  acceptance_criteria: []
output:
  actions: []
  changed_files: []
  decisions: []
  evidence: []
  validation: []
  risks: []
  handoff:
    status: ""
    next_step: ""
    blockers: none
    read_next: []
```

### Engineer I/O 最小字段

```yaml
schema: opc.engineer_io.v1
role: Engineer
input:
  task_scope: ""
  acceptance_criteria: []
  implementation_constraints: []
  source_files: []
  upstream_architect_output: []
output:
  implementation_summary: []
  changed_files: []
  validation_commands: []
  validation_results: []
  commit: ""
  remaining_risks: []
  next_role_input: []
```

### QA / Reviewer I/O 最小字段

```yaml
schema: opc.qa_io.v1
role: QA | Reviewer
input:
  acceptance_criteria: []
  implementation_artifacts: []
  changed_files: []
  validation_scope: []
output:
  checks: []
  validation_results: []
  defects_or_risks: []
  pass_fail: pass | fail | blocked
  evidence: []
  handoff: ""
```

### Architect I/O 最小字段

```yaml
schema: opc.architect_io.v1
role: Architect
input:
  user_request: ""
  constraints: []
  existing_context: []
output:
  architecture_split: []
  module_responsibilities: []
  interface_or_data_structure: []
  technical_decisions: []
  risks_and_tradeoffs: []
  engineer_input: []
```

角色 I/O artifact 不替代任务清单、验收文档或发布检查；它用于记录角色边界、输入来源、输出去向和可恢复上下文。缺少参与角色的 I/O artifact 时，对应任务不得标记为完成。

长任务或跨会话任务还应补充可恢复字段：

| 字段 | 长任务要求 | 含义 |
| --- | --- | --- |
| `id` | 必填 | 稳定任务编号，用于跨会话引用、验收记录、commit message 和后续任务依赖。 |
| `depends_on` | 必填 | 前置任务 ID 列表；无依赖时写 `none`，不得只用自然语言描述依赖。 |
| `read_before_start` | 必填 | 开始或继续任务前必须读取的任务条目、依赖产物、相关文件、pending diff 或验收记录。 |
| `execution` | 必填 | 执行主体或协作方式，例如主会话、Explore subagent、skill、人工评审或 QA 验收。 |
| `evidence` | 完成时必填 | 完成后的产物、验证方式、验证结果；无法验证时写明未验证原因。 |
| `handoff` | 跨会话时必填 | 当前状态、下一步、阻塞项、需重读文件和最近验证结果，用于清空上下文后继续。 |

### 任务 ID 命名规则

- 普通阶段任务使用 `P<阶段>-<分组>-<序号>`，例如 `P8-4-4` 表示 P8 第 4 组第 4 条任务。
- 专题追加任务可使用稳定前缀加两位序号，例如 `LT-01`、`LT-02`；同一专题内不得复用 ID。
- 任务 ID 一经进入任务清单、验收记录、commit message 或后续任务的 `depends_on`，后续只允许补充说明，不应改名。
- 跨会话继续、验收文档、commit message 和后续任务引用必须使用任务 ID，而不是只写任务标题。

### `read_before_start` 前置读取规则

- 开始任务前必须先读取当前任务条目，确认 `id`、`depends_on`、`execution` 和完成标准。
- `depends_on` 不为 `none` 时，必须读取前置任务的产物、`evidence`、验收记录或对应 diff。
- 继续跨会话任务前必须读取任务声明中的相关文件、当前 pending diff，以及最近一次 `handoff` 或验收结论。
- 若某个必读文件或记录不存在，应在 `evidence` 或 `handoff` 中说明缺失原因，不得依赖聊天历史补全。
- 清空上下文后的继续流程应遵守 [discipline.md#上下文清空后继续协议](discipline.md#上下文清空后继续协议)。

### `execution` 执行主体规则

- `main`：由主会话直接执行，适用于需要综合判断、写入文件、提交变更或维护当前上下文的任务。
- `explore`：由 Explore subagent 只读检索或定位信息，适用于独立搜索；不得作为长期上下文保存器或直接提交实现。
- `skill`：调用项目 skill 产出结构化结果，适用于 task-spec、implementation-check、acceptance-check 等已有流程。
- `manual_review`：需要人工评审、取舍或审批后才能继续，适用于规则进入项目级标准、风险策略或外部动作。
- `qa_acceptance`：由 QA 角色或验收 skill 做只读验收，输出 pass/fail、证据和阻塞项，不直接修改实现。
- subagent 和 skill 的使用边界应遵守 [discipline.md#subagent-使用边界](discipline.md#subagent-使用边界)。

### `evidence` 完成证据规则

- 每个已完成任务必须记录 `evidence`；未完成任务可以保留空占位或省略。
- `evidence` 至少包含产物路径、验证方式和验证结果，例如修改文件、检查命令、人工验收结论。
- 若任务无法验证，必须写明未验证原因、影响范围和后续补验方式。
- 证据应引用可重新读取的文件、命令输出摘要或验收记录，不应只写“已完成”。

### `handoff` 跨会话交接规则

- 任务可能跨会话、阶段性压缩或清空上下文继续时，必须在任务条目、验收记录或交接记录中维护 `handoff`。
- `handoff` 至少说明当前状态、下一步、阻塞项、需重读文件和最近验证结果。
- 无阻塞项时写 `none`；最近验证失败或未执行时，必须写明失败原因或未验证原因。
- `handoff` 应保证后续执行者只依赖任务文件和产物即可恢复，不依赖聊天历史。
- 阶段性压缩或换会话触发条件应遵守 [discipline.md#阶段性压缩与换会话触发条件](discipline.md#阶段性压缩与换会话触发条件)。

> 参考样例：[tasks-p4.md](../../tasks-p4.md)、[tasks.example.md](../../tasks.example.md)

## 验收文档应至少包含

- 验收对象
- 验收标准
- 检查方法
- 结果记录
- 是否通过

> 参考样例：[docs/completed_tasks/tasks-p2.md](../completed_tasks/tasks-p2.md)（含验收项条目）

## 决策文档应至少包含

- 审查对象
- 决策结论
- 决策理由
- 风险判断
- 后续建议

> 参考样例：[docs/plan/organization.md](../plan/organization.md)

## Workflow Pack 应至少包含

- Manifest：id、kind、owner_roles、inputs、outputs、permissions、acceptance、trace
- 适用场景：何时使用，何时不使用
- 角色边界：哪些由 Claude 协作 skill 完成，哪些由 OPC runtime workflow 完成
- 权限边界：只读、写入、命令执行、审批动作分别如何声明
- 验收方式：可复现命令、检查路径或人工验收项

> 参考样例：[docs/plan/workflow.md](../plan/workflow.md#9-workflow-pack-使用规范)

## 发布检查应至少包含

- 发布对象
- 发布前检查项
- 运行验证方式
- 监控关注点
- 回滚条件
- 发布结论

Release report artifact 应至少包含：

| 字段 | 含义 |
| --- | --- |
| `schema` | 报告 schema 版本，例如 `opc.release_report.v1` |
| `version` / `commit` | 发布版本与 git commit |
| `checks[]` | 检查项、命令、结果、是否阻塞、skip 原因 |
| `blocking_items[]` | 当前阻塞发布的问题 |
| `supplemental_validation[]` | 需要 CI、Docker、真实 Qt 或目标环境补验的项 |
| `recommendation` | `ready`、`needs-env` 或 `not-ready` |
| `notes` | 发布边界、风险和人工确认说明 |

> 参考样例：[docs/runs/harness_interactive_mode.md](../runs/harness_interactive_mode.md)

## 研究建议应至少包含

- 用户反馈或市场信息摘要
- 增长假设
- 实验方案
- 观察指标
- 后续产品或需求建议
- 风险与边界

> 参考样例：[docs/plan/success.md](../plan/success.md)
