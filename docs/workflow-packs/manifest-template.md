# Workflow Pack Manifest Template

复制本模板创建新的 workflow pack，并将占位内容替换为具体任务类型说明。

## Manifest

| 字段 | 值 |
| --- | --- |
| `id` | `<pack-id>` |
| `kind` | `claude_skill` / `opc_runtime_workflow` |
| `owner_roles` | `<PM / Engineer / QA / Ops / Architect / Growth>` |
| `inputs` | `<任务描述、目标文件、约束、验收标准、环境信息>` |
| `outputs` | `<代码变更、评审记录、文档更新、验收记录、发布检查>` |
| `permissions` | `<read_only / write_files / run_commands / approval_required>` |
| `acceptance` | `<可检查完成标准>` |
| `trace` | `<需要记录的 run event、artifact 或人工决策>` |

## 适用场景

- `<该 pack 适合的任务类型>`
- `<触发该 pack 的输入信号>`

## 不适用场景

- `<应转交其他 pack 或 skill 的场景>`
- `<禁止自动执行的高风险场景>`

## 角色边界

| 角色 | 责任 | 禁止事项 |
| --- | --- | --- |
| `<role>` | `<必须产出>` | `<不得越界的行为>` |

## 输入要求

- `task_description`：`<用户目标或任务描述>`
- `context`：`<相关文件、PRD、bug、PR、环境信息>`
- `constraints`：`<安全、范围、兼容性、性能、时间限制>`
- `acceptance_criteria`：`<可验证标准>`

## 输出要求

- `<输出 1>`：`<格式或证据要求>`
- `<输出 2>`：`<格式或证据要求>`
- `<结论>`：`<pass / fail / needs-info / ready 等允许值>`

## 权限边界

- 默认权限：`<read_only>`
- 写入权限：`<允许写入的文件类型或目录；无则写无>`
- 命令权限：`<允许执行的验证命令；无则写无>`
- 人工确认：`<触发确认的动作，例如 push、部署、删除、迁移>`

## 验收标准

- `<标准 1>`
- `<标准 2>`
- `<标准 3>`

## Trace / Artifact 要求

- `run_events.jsonl`：`<关键事件>`
- `run_trace.json`：`<决策、失败、回退或人工确认>`
- `artifacts`：`<PRD、实现摘要、QA 报告、release-check 等文件>`

## 转交规则

- `<从 skill 转 runtime workflow 的条件>`
- `<从 review 转 bugfix / docs-update / release-check 的条件>`
- `<信息不足时如何返回用户或上游角色>`
