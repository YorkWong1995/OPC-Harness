# Bugfix Workflow Pack

## Manifest

| 字段 | 值 |
| --- | --- |
| `id` | `bugfix` |
| `kind` | `opc_runtime_workflow` |
| `owner_roles` | `Engineer`, `QA`, 必要时 `PM` |
| `inputs` | 缺陷描述、复现路径、预期行为、实际行为、相关文件、验收标准 |
| `outputs` | 根因说明、最小代码变更、定向验证结果、QA 验收记录、必要的复盘记录 |
| `permissions` | 允许写入缺陷相关文件和运行定向验证命令；危险操作需要人工确认 |
| `acceptance` | 缺陷可复现或可定位，修复范围最小，定向验证通过，QA 给出明确结论 |
| `trace` | stage_started、stage_completed、tool_call、validation_failed、qa_failed、rollback_decision、approval_decision |

## 适用场景

- 用户提供明确缺陷、复现路径或失败测试。
- 现有功能与 PRD、任务验收标准或文档约定不一致。
- 需要保留 run_id、artifacts、trace、Engineer 输出和 QA 验收记录。

## 不适用场景

- 新功能开发、产品方向讨论或需求取舍。
- 大范围重构、依赖升级或无关清理。
- 只有只读评审需求时应使用 review pack 或 `/review` skill。
- 只需要起草缺陷定位模板且不修改代码时，可只使用 `/bugfix` skill。

## Runtime Workflow 与 Skill 边界

- 使用 `bugfix` runtime workflow：需要真实修改代码、运行验证、生成 artifacts、支持 QA fail 回退或复盘沉淀。
- 只使用 `/bugfix` skill：缺陷范围很小、用户只需要协作式定位/修复建议，或不需要 run trace 和 artifacts。
- 若 bugfix 过程中发现需求不清或验收标准冲突，回退 PM 或请求用户确认。
- 若修复后需要发布检查，转交 release-check pack。

## 角色边界

| 角色 | 责任 | 禁止事项 |
| --- | --- | --- |
| PM | 澄清预期行为、验收标准和缺陷影响范围 | 不指定未经验证的技术修复方案 |
| Engineer | 复现/定位根因，实施最小修复，提供定向验证证据 | 不做无关重构、格式化、依赖升级或顺手优化 |
| QA | 根据验收标准复核修复结果，输出 pass/fail 和 evidence | 不直接修复代码，不把缺失验证判为通过 |

## 输入要求

- `defect_description`：缺陷现象和影响范围。
- `reproduction`：复现命令、操作步骤、日志或失败测试。
- `expected_behavior`：预期结果或验收标准。
- `related_files`：已知相关文件、模块或配置。
- `constraints`：不能触碰的范围、性能/兼容性/安全约束。

## 输出要求

- `root_cause`：根因判断和证据。
- `fix_summary`：最小修复范围和变更文件。
- `validation`：定向验证命令、关键输出和结果。
- `qa_report`：QA 检查项、证据、缺陷列表和结论。
- `next_action`：`done` / `rework` / `needs-info`。

## 权限边界

- 默认允许读取相关代码、日志、测试和文档。
- 允许写入与根因直接相关的代码、测试或文档。
- 允许运行定向测试、lint 或复现命令。
- 删除文件、重置 git、push、发布、迁移、修改共享环境必须人工确认。

## 验收标准

- 根因说明能对应到具体代码、配置、文档或环境约束。
- 修复范围只覆盖缺陷直接原因。
- 至少有一条定向验证证据证明缺陷已修复或风险已隔离。
- QA 结论为 `pass` 时不得存在未处理 blocking defect。

## Trace / Artifact 要求

- `run_events.jsonl`：记录 stage_started、tool_call、stage_completed、validation_failed、qa_failed。
- `run_trace.json`：记录 QA 退回、人工确认、回退决策和最终状态。
- `artifacts`：保存 PRD/缺陷说明、Engineer 输出、QA 验收记录、run_metrics.json。

## 转交规则

- 信息不足：回退 PM 或请求用户补充复现路径/预期行为。
- 需要写代码：继续 bugfix runtime workflow。
- 只读评审：转 review pack 或 `/review` skill。
- 涉及发布：QA 通过后转 release-check pack。
