# Agent Assets

`.claude/agents/` 保存项目级可复用 agent 资产说明。它不是 OPC runtime agent 实现，也不是 Claude skill；它用于把角色职责、输入输出、工具边界和禁止事项沉淀为可复用配置样板。

## 与其他资产的区别

| 类型 | 作用 | 是否执行 |
| --- | --- | --- |
| Skill | 面向 Claude 协作的可调用能力，如 `/review`、`/bugfix` | 由 Claude Code skill 执行 |
| Agent asset | 项目内角色/任务配置说明，供复用或迁移到其他 agent 系统 | 不直接执行 |
| Runtime agent | OPC 代码中的实际角色 agent 和 prompt/tool 配置 | 由 OPC workflow 执行 |
| Workflow pack | 一类任务的流程、角色、权限、验收和 trace 边界 | 可只读说明，也可由 runtime workflow 执行 |

## 字段模板

每个 agent asset 至少包含：

- `id`：稳定标识，如 `pm`、`engineer`、`qa`。
- `source_role`：对应的 OPC runtime 角色或文档角色。
- `purpose`：适用场景和不适用场景。
- `inputs`：进入该角色前必须具备的信息。
- `outputs`：该角色必须产出的结构化结果。
- `tool_boundary`：可读取、可写入、可执行或必须审批的工具边界。
- `handoff`：向上游/下游角色交接的条件。
- `forbidden`：明确禁止事项。
- `acceptance`：该 asset 是否可被复用的检查标准。

## 维护规则

- Agent asset 只描述稳定角色边界，不复制一次性任务状态或 run artifact。
- 若 runtime prompt、角色职责或工具边界改变，应同步更新对应 asset。
- 若需要真实执行，应使用 OPC runtime agent、workflow pack 或 skill，而不是把 asset 当命令运行。
- 新增 asset 后同步更新本 README 和项目文档索引。
