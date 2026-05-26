# Docs Update Workflow Pack

## Manifest

| 字段 | 值 |
| --- | --- |
| `id` | `docs-update` |
| `kind` | `opc_runtime_workflow` |
| `owner_roles` | `PM`, `QA`, 必要时 `Architect` |
| `inputs` | 文档漂移描述、目标文档、相关实现或规范、索引位置、验收标准 |
| `outputs` | 更新后的文档、链接/索引检查结果、变更摘要、QA 验收记录 |
| `permissions` | 允许写入文档和索引；运行文档结构检查；危险操作需要人工确认 |
| `acceptance` | 文档内容准确，链接和索引可找到，变更范围与任务一致，QA 通过 |
| `trace` | stage_started、stage_completed、tool_call、validation_failed、qa_failed、approval_decision |

## 适用场景

- 文档与代码、配置、流程或任务结果不一致。
- 新增 skill、workflow pack、script、agent asset 后需要同步索引。
- 需要把规范、使用方式、验收字段或边界说明沉淀到项目文档。

## 不适用场景

- 需要修改运行时代码或修复缺陷，应转 bugfix pack。
- 只需要只读评审，应使用 review pack 或 `/review` skill。
- 需要执行发布检查，应转 release-check pack。

## 角色边界

| 角色 | 责任 | 禁止事项 |
| --- | --- | --- |
| PM | 明确文档目标、读者、范围和验收标准 | 不把未确认的临时 run 状态写成长期规范 |
| Architect | 校对架构、workflow、权限边界和命名一致性 | 不借文档任务重设计 runtime 架构 |
| QA | 检查链接、索引、字段完整性和变更范围 | 不把无法定位的文档入口判为通过 |

## 输入要求

- `doc_target`：要新增或更新的文档路径。
- `source_of_truth`：代码、规范、任务、PRD、run artifact 或用户确认信息。
- `index_targets`：README、DOCS_STRUCTURE、目录 README 等入口。
- `acceptance_criteria`：内容准确性、可发现性、链接/索引检查要求。

## 输出要求

- `doc_changes`：新增或修改的文档范围。
- `index_updates`：索引入口和链接检查结果。
- `validation`：定向文档结构测试、链接检查或人工核对证据。
- `qa_report`：验收对象、标准、方法、结果和结论。

## 权限边界

- 允许写入 `.md` 文档、目录 README 和必要索引。
- 不默认修改运行时代码、测试、配置或脚本。
- 若文档更新要求改变行为，必须拆分为单独实现任务。
- 删除文档、移动公开入口或修改发布脚本必须人工确认。

## 验收标准

- 文档内容与当前代码或已确认规范一致。
- 用户能从 README、DOCS_STRUCTURE 或目录 README 找到目标文档。
- 新增链接、索引或路径可定位。
- 验收记录包含检查方法和证据。

## Trace / Artifact 要求

- `run_events.jsonl`：记录文档读取、写入、验证和 QA 阶段。
- `run_trace.json`：记录信息不足、人工确认或 QA fail 回退。
- `artifacts`：保存文档变更摘要、验证结果和 QA 报告。

## 转交规则

- 发现代码缺陷：转 bugfix pack。
- 发现只读风险：转 review pack。
- 文档变更准备发布：转 release-check pack。
- 信息来源不明确：回退 PM 或请求用户确认 source of truth。
