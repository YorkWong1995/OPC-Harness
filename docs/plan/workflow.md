# 最小 Harness 工作流

## 1. 工作流目标

MVP 阶段不追求复杂自治，而是先建立一条可以稳定重复执行的最小闭环。该闭环的目标，是让一个需求可以经过结构化、设计、拆解、实现、验证和复盘，形成可回放、可修正、可复用的工作流。

最小 harness 工作流需要满足以下要求：

- 每一步都有明确责任角色
- 每一步都有标准输入与标准输出
- 每一步都知道何时继续、何时回退、何时升级
- 关键节点允许人工确认
- 最终结果能够被验证，而不是只被描述

## 2. MVP 角色配置

默认最小可验证交付闭环为 **PM → Engineer → QA**：

| 角色 | 标准输入 | 标准输出 | 通过条件 | 失败路径 |
| --- | --- | --- | --- | --- |
| PM | 用户目标、业务问题、约束条件 | PRD、范围说明、验收标准 | 目标明确、范围可控、验收标准可检查 | 信息不足时继续澄清；范围冲突时升级用户确认 |
| Engineer | PM 输出、代码上下文、QA defects | 代码变更、实现摘要、测试或验证结果 | 实现完成且验证证据可复现 | 实现失败时终止或人工介入；QA fail 后带 defects 返工 |
| QA | PM 验收标准、Engineer 输出、验证结果 | pass/fail、checked_items、evidence、defects、next_action | 结论明确且证据覆盖关键验收标准 | fail 回流 Engineer；验收标准冲突时升级 PM 或用户 |

按需动态加入：

| 可选角色 | 自动触发语义 | 关键词兜底示例 |
| --- | --- | --- |
| Architect | 任务存在明显设计问题、系统/接口边界不清、数据结构或技术取舍影响较大 | 架构、系统设计、设计方案、模块边界、接口边界、数据结构、技术方案、技术取舍、重构、architecture |
| Ops | 任务涉及部署、发布、上线、环境确认、运行检查、监控、回滚或运维风险 | 部署、发布、上线、环境、运行检查、运行风险、监控、回滚、运维、deploy、release |
| Growth | 任务涉及用户研究、用户反馈、增长、竞品、转化指标、产品实验或市场反馈假设 | 增长、市场、用户研究、用户反馈、竞品、转化、指标、产品实验、反馈假设、growth、research |
| CEO / 用户 | 负责范围确认、优先级排序与关键决策 | `--ceo-review` 或人工确认节点 |

动态角色只补充主链路所需的输入或评审，不替代 PM → Engineer → QA 的默认交付闭环。

### 2.1 自动识别与手动覆盖

- 自动识别：`opc run` 根据任务描述调用可选角色分类器；分类器不可用或返回无效时，使用上表关键词兜底。
- 手动启用：`--with-architect`、`--with-ops`、`--with-growth` 用于在用户已明确需要对应角色时强制加入。
- 手动关闭：`--skip-architect` 用于简单任务或用户明确不需要架构环节时移除 Architect。
- CEO 审查：`--ceo-review` 只加入关键决策审查，不参与默认实现链路，也不替代用户最终确认。
- 优先级：显式 `--with-*` 和 `--skip-architect` 覆盖自动识别结果；配置中的 `all` 仍可被 `--skip-architect` 移除 Architect。

## 3. 六步最小闭环

### 第 1 步：需求结构化

- 责任角色：PM
- 输入：用户目标、业务问题、约束条件
- 输出：PRD、范围说明、验收标准
- 继续条件：目标明确、范围可控、验收标准可检查
- 回退条件：目标模糊、边界不清、缺少关键约束
- 升级条件：目标冲突、优先级冲突、范围明显失控

### 第 2 步：方案判断

- 责任角色：Architect 或 PM
- 输入：PRD、现有约束、已有系统信息
- 输出：架构说明或简化实现方案
- 继续条件：存在可执行路径，复杂度与 MVP 匹配
- 回退条件：方案依赖不明、实现路径不清
- 升级条件：出现高影响技术取舍，需要用户确认

说明：
- 若任务非常小，可跳过完整架构设计，由 PM + Engineer 直接进入任务拆解。
- 若任务涉及接口、模块边界或数据结构，建议保留此步。

### 第 3 步：任务拆解

- 责任角色：Planner、PM 或 Architect
- 输入：PRD、方案说明
- 输出：任务清单、责任角色、依赖关系、完成标准
- 继续条件：任务可执行、顺序清晰、完成标准明确
- 回退条件：任务粒度过大、依赖不清、责任不明
- 升级条件：拆解后发现范围超出 MVP

### 第 4 步：实现执行

- 责任角色：Engineer
- 输入：任务清单、方案说明、代码上下文
- 输出：代码变更、实现说明、最小验证结果
- 继续条件：实现完成且具备最小验证证据
- 回退条件：实现被阻塞、方案无法落地、上下文缺失
- 升级条件：需要改动超出原范围，或触发高风险操作

### 第 5 步：验证验收

- 责任角色：QA
- 输入：PRD、验收标准、代码变更、验证结果
- 输出：验收记录、缺陷清单、通过/退回结论
- 继续条件：验收通过，关键标准满足
- 回退条件：存在功能缺陷、验收失败、验证证据不足
- 升级条件：验收标准与实现结果冲突，需要 PM 或用户裁决

### 第 6 步：复盘沉淀

- 责任角色：PM、QA 或 CEO / 用户
- 输入：任务结果、验收结论、执行问题、日志记录
- 输出：复盘记录、经验总结、流程修正项
- 完成条件：明确本轮是否成功、问题在哪里、下轮如何改进
- 回退条件：无
- 升级条件：若暴露系统性问题，升级为流程或规范修订任务

## 4. 标准状态流转

推荐使用以下状态流转描述每一次任务：

`待澄清 → 已定义 → 已设计 → 已拆解 → 实现中 → 待验收 → 已通过 / 已退回 → 已复盘`

含义：

- **待澄清**：目标还不够清楚
- **已定义**：PRD 已具备
- **已设计**：方案明确
- **已拆解**：任务清单可执行
- **实现中**：Engineer 正在完成工作
- **待验收**：实现完成，等待 QA 检查
- **已通过 / 已退回**：验收结果明确
- **已复盘**：经验已经沉淀

## 5. 人工确认节点

最小工作流中，以下节点默认需要人工确认或允许人工插入判断：

1. PRD 完成后，确认目标与范围
2. 高影响技术方案出现时，确认取舍
3. 实现阶段需要高风险操作时，确认是否执行
4. 验收结论存在争议时，确认是否通过或调整标准
5. 复盘时，确认哪些经验要上升为项目规范

## 6. 回退路径

当工作流出现问题时，默认按以下路径回退：

- 需求问题：退回 PM
- 方案问题：退回 Architect 或 PM
- 任务定义问题：退回 Planner / PM
- 实现问题：退回 Engineer
- 验收标准问题：退回 PM
- 运行或发布问题：退回 Ops / Engineer

原则：
- 回退到"问题真正产生的上游节点"，而不是只在末端修补。

## 7. MVP 运行方式

在 MVP 阶段，建议每次只选择一个足够小但完整的任务运行这条工作流。一次运行应满足：

- 有一个清晰目标
- 有一个对应 PRD
- 有一个任务清单
- 有一次真实实现
- 有一次真实验收
- 有一次复盘记录

建议优先选择：

- 单页面功能
- 单接口功能
- 小型后台能力
- 一次明确的文档到实现任务

不建议一开始就选择：

- 跨多个系统的大型项目
- 高并发、分布式、复杂部署问题
- 需要完整平台能力的任务

## 8. 一次工作流是否成功的判断标准

一次最小 harness 工作流成功，不要求结果完美，但至少要满足：

- 工作流完整走通
- 每一步责任角色清楚
- 文档产物完整
- 验收结论明确
- 问题能被定位到具体环节
- 复盘后能形成下一轮优化输入

## 9. Workflow Pack 使用规范

Workflow pack 是可复用的工作流说明单元，用来把一类任务的输入、角色、权限、产物和验收标准固定下来。P6 第一版只定义规范和样例边界，不把所有 pack 都内置为 runtime 自动编排。

### 9.1 Manifest 最小字段

| 字段 | 含义 |
| --- | --- |
| `id` | 稳定标识，如 `bugfix`、`review`、`docs-update` |
| `kind` | `claude_skill` 或 `opc_runtime_workflow` |
| `owner_roles` | 主要责任角色 |
| `inputs` | 任务描述、目标文件、约束、验收标准等输入 |
| `outputs` | 代码变更、评审记录、文档更新、验收记录等输出 |
| `permissions` | 只读、写入、命令执行或需要审批的能力 |
| `acceptance` | 可检查的完成标准 |
| `trace` | 需要落入 run trace 的关键事件或 artifact |

### 9.2 三类基础 Pack

| Pack | kind | 使用场景 | 标准输出 |
| --- | --- | --- | --- |
| `bugfix` | `opc_runtime_workflow` | 有明确缺陷、复现路径和预期行为的修复 | 根因说明、最小代码变更、定向测试、QA 验收记录 |
| `review` | `claude_skill` | PR、pending diff 或任务结果的评审 | 风险清单、阻塞问题、非阻塞建议、是否通过 |
| `docs-update` | `opc_runtime_workflow` | 文档漂移、规范补充、使用说明更新 | 变更后的文档、链接/索引检查、验收说明 |

### 9.3 Claude 协作 Skill 与 OPC Runtime Workflow 边界

- Claude 协作 skill 适合只读评审、文档模板生成、角色切换等“协作者行为”，由 `.claude/skills/` 执行。
- OPC runtime workflow 适合需要 run_id、artifact、trace、角色产物和 QA 回退的任务，由 `opc run` 执行。
- review pack 第一版推荐作为 Claude 协作 skill 执行；如果评审需要写入代码或触发回归，则转为 bugfix 或 docs-update runtime workflow。
- 每个 pack 都必须声明权限边界，未声明写入或命令执行权限时默认只读。

## 10. Thread / Session / Run / Artifact / Checkpoint 边界

| 概念 | OPC 语义 | 用户可见入口 | 是否长期保存 |
| --- | --- | --- | --- |
| Thread | 同一目标下多次 run 的逻辑讨论线，P6 仅作为规划概念 | 暂无一等命令 | 否，P6 不持久化 thread |
| Session | 一次 CLI/交互式使用过程，可能包含一次或多次命令 | shell / UI 会话 | 否，关闭后不作为 OPC 状态恢复单位 |
| Run | 一次 `opc run` 或 `opc resume` 的执行实例，拥有 run_id 和 artifacts | `opc run`、`opc resume`、`opc runs list` | 是，保存在 artifacts |
| Artifact | run 产生的报告、角色输出、metrics、trace、state | `workspace/<project>/artifacts/` | 是，作为复盘和验收证据 |
| Checkpoint | 可恢复状态快照，目前对应 `.opc_state.json` | `opc resume` | 是，但只服务恢复，不等同长期 memory |

使用规则：

- 新需求、新目标或验收标准变化明显时新建 run。
- 中断、失败修复或 QA 退回后继续同一目标时使用 resume。
- `run_events.jsonl`、`run_trace.json`、`run_metrics.json` 用于回放和复盘，不写入长期 memory。
- Artifact 是证据，memory 是经确认的长期偏好/项目决策；二者不能混用。
- P6 不提供 thread 级长期记忆或团队协作语义，避免把单次 run 扩展为多用户工作台。

## 11. 统一阶段执行契约

P6/P7 的 runtime 协议以 `StageContract` 描述每个 DAG 阶段的可执行边界。第一步先把契约结构落到 `workflow_spec.py`，运行时再分步绑定角色输出和 trace 事件。

### 11.1 StageContract 字段

| 字段 | 含义 |
| --- | --- |
| `name` | 阶段稳定标识，如 `pm`、`engineer`、`qa` |
| `role` | 执行该阶段的责任角色 |
| `input_schema` | 阶段输入 schema，如 `ContextPack` 或 `WorkflowState` |
| `tools` | 允许该阶段使用的工具名列表 |
| `output_schema` | 阶段输出 schema，如 `PMOutput`、`EngineerOutput`、`QAOutput` |
| `artifact` | 阶段产物名，用于 `artifact_paths` 和 trace inspect |
| `validation` | 阶段校验规则名，如必填字段、证据、失败分支等 |
| `transition` | `TransitionPolicy`，定义 pass/fail/error/timeout 后的状态 |
| `conditional_branches` | 按角色输出字段选择的条件分支，如 QA `next_action` |
| `failure_branch` | 阶段失败时建议进入的回退状态 |
| `retry_policy` | 最大重试次数和耗尽后的处理动作 |
| `parallel_group` | 可并行阶段组，如 `growth_architect` |
| `sub_workflow` | 子工作流标识，预留给嵌套 DAG |

### 11.2 StageResult 与 StageValidation

`StageResult` 是阶段执行后的结构化记录，至少包含阶段名、状态、结构化输出、artifact 路径、校验结果、下一状态和失败原因。`StageValidation` 使用 `passed/failed/skipped` 表达校验结论，并记录缺字段、schema 错误或非法 transition 诊断。

### 11.3 TransitionPolicy

`TransitionPolicy` 统一表达 `on_pass`、`on_fail`、`on_error`、`on_timeout`、`failure_branch`、`retry_limit` 和 `approval_required`。任何目标状态都必须存在于 workflow spec 的 `states` 中；非法 transition 不允许进入运行时。

### 11.4 默认阶段契约

默认契约覆盖 `pm`、`growth`、`architect`、`engineer`、`qa`、`ops`、`retro`。核心链路保持 PM → Engineer → QA → Retro，小步接入完整 DAG 字段：

- PM 输出 `PMOutput`，通过后进入 `已定义`。
- Engineer 输出 `EngineerOutput`，失败或阻塞进入 `已退回`。
- QA 输出 `QAOutput`，`next_action=done` 进入 `已通过`，`rework` 或 `human_intervention` 进入 `已退回`。
- Architect/Growth 可进入 `growth_architect` 并行组，但不替代主链路。
- Ops 仅在运行、部署或回滚检查需要时加入。

## 12. 人工审批、熔断与回退决策记录

P6 运行时必须把“停在哪里、为什么停、默认动作是什么”写入 trace，避免人工接管时只能从日志猜测。

| 事件 | 触发条件 | 关键字段 | 默认行为 |
| --- | --- | --- | --- |
| `approval_required` | 人工 review、CEO review、auto-confirm 审批点 | `stage`、`mode`、`default_action` | 未批准不继续；auto-confirm 记录为自动继续 |
| `approval_decision` | 用户、CEO 或 auto-confirm 给出决策 | `stage`、`decision`、`actor`、`result` | `y` 继续，`n` 停止，`r` 回退，`e` 编辑后重做 |
| `circuit_breaker_open` | 超过 workflow 轮次、成本硬上限、QA 返工上限或协议校验失败 | `reason`、`stage`、`limit/current`、`default_action` | 默认停止 workflow，等待人工接管 |
| `rollback_decision` | 用户请求回退或 QA fail 需要返工 | `from_stage`、`to_stage`、`reason`、`default_action` | 清理目标阶段完成标记并重跑目标阶段 |

## 13. run_metrics token / model / cost 字段结构

`run_metrics.json` 是 run 级运行指标 artifact，用于验收、复盘、trace inspect 和成本趋势分析。成本字段仅表示本地估算，不等同供应商账单。

### 13.1 分阶段字段

每个 `stages.<stage_name>` 条目至少支持以下字段：

| 字段 | 类型 | 含义 | 兼容规则 |
| --- | --- | --- | --- |
| `model` | string | 阶段实际使用或声明的模型 | 缺失时写入 `unknown` |
| `input_tokens` | integer | 阶段输入 token | 缺 usage 时为 `0` |
| `output_tokens` | integer | 阶段输出 token | 缺 usage 时为 `0` |
| `duration_seconds` | number | 阶段耗时秒数 | 缺失时为 `0` |
| `tool_calls` | integer | 阶段工具调用数 | 缺失时为 `0` |
| `api_calls` | integer | 阶段 API 调用数 | 缺失时为 `0` |
| `estimated_cost` | number / null | 阶段估算成本 | 未启用估算或未知价格时为 `null` |
| `currency` | string / null | 成本币种 | 未启用估算时为 `null` |
| `pricing_source` | string | 价格来源 | 未知价格时写 `unknown` |

### 13.2 总计字段

`totals` 汇总所有非内部阶段日志，支持两级统计：

| 字段 | 汇总规则 |
| --- | --- |
| `input_tokens` | 所有阶段 `input_tokens` 求和 |
| `output_tokens` | 所有阶段 `output_tokens` 求和 |
| `duration_seconds` | 所有阶段耗时求和并保留两位小数 |
| `tool_calls` | 所有阶段工具调用求和 |
| `api_calls` | 所有阶段 API 调用求和 |
| `estimated_cost` | 已知阶段成本求和；任一阶段未知但启用估算时保留已知和并记录异常；未启用时为 `null` |
| `currency` | 成本估算启用时使用配置币种，否则为 `null` |
| `pricing_source` | 使用配置来源；存在未知模型价格时标注 `partial` 或 `unknown` |

### 13.3 成本估算边界

- 成本估算默认依赖显式配置的模型价格，不把临时供应商价格当作永久事实。
- 未启用估算、模型价格缺失或 usage 缺失时，不伪造成本数字。
- `token-report`、`trace inspect` 和 cost trend 命令只能读取已有 metrics，不重新调用模型或 workflow。
- 旧 `run_metrics.json` 缺少 model/cost 字段时必须兼容读取，并在报告中标注缺失字段。

## 14. Memory、RAG、Session、Checkpoint 与 Artifact 边界

- Memory：保存经过确认、可跨任务复用的 user/project/workflow 事实，必须带 scope、source、confidence 和生命周期字段。
- RAG：检索当前项目文件或文档片段，解决“在哪里找事实”，不替代长期记忆。
- Session：一次 CLI/IDE 交互过程，关闭后不作为 OPC 状态恢复单位。
- Checkpoint：`.opc_state.json`，只服务 `opc resume`，不等同长期 memory。
- Artifact：PRD、实现说明、QA 报告、metrics 和 trace，是 run 证据；短期 run 状态默认不写入长期 memory。

任务结果回流必须遵守 artifact / RAG / memory 分层：run 产物先作为 artifact 保存；只有用户显式选择的项目文件进入 RAG 索引；只有经过确认、可跨任务复用的用户偏好、项目决策、workflow 经验或外部引用才能成为长期 memory。复盘阶段可以产生 memory 候选审计事件，但未确认候选不得自动写入 `memory.jsonl`。

## 15. Trace Inspect 只读能力定义

Trace Inspect 是面向人工接管和失败定位的只读视图，第一版命令形态为 `opc trace inspect --artifacts-dir <path>`。它只能读取已有 `run_events.jsonl`、`run_trace.json`、`run_metrics.json`、`.opc_state.json` 和 artifact 路径，不得重新调用模型、工具、测试或写入 run 状态。

### 15.1 Inspect 数据模型

| 字段 | 来源 | 含义 |
| --- | --- | --- |
| `run_id` | trace / events | 当前 run 标识 |
| `final_status` | trace / state | run 最终状态或当前暂停状态 |
| `timeline` | `stage_started`、`stage_completed`、`stage_summary_created` | 阶段时间线、角色、状态和摘要 |
| `artifacts` | `.opc_state.json.artifact_paths` | PRD、实现说明、验收记录、ops/retro 等产物路径 |
| `tool_calls` | `tool_call`、`guardrail_*` | 工具调用、阻断、警告和审批要求 |
| `decisions` | `approval_required`、`approval_decision`、`rollback_decision`、`circuit_breaker_open` | 人工审批、回退和熔断决策 |
| `failures` | `validation_failed`、`qa_failed`、`workflow_stopped`、`cost_hard_limit` | 失败点、诊断、默认停止原因 |
| `metrics` | `run_metrics.json` / trace metrics | token、耗时、工具调用、人工介入和返工次数 |
| `compatibility` | 缺失字段检测 | 旧 trace 或缺失事件的兼容提示 |

### 15.2 输出要求

- 默认输出阶段时间线、最近失败点、决策事件、artifact 路径和指标摘要。
- `--json` 输出稳定 JSON，供后续 UI 或自动化评估读取。
- `--focus failures|decisions|tools|artifacts` 只过滤展示，不改变底层 trace。
- 缺失 `run_trace.json` 时可从 `run_events.jsonl` 降级重建；缺失 metrics/state 时必须给出兼容提示。
- Inspect 不重跑、不修复、不审批、不删除文件；所有后续动作必须由单独命令或人工显式触发。
