# P3: OPC 定位收敛与运行时产品化优化

> 来源：围绕 OPC 当前定位、Harness Engineering、角色协作、可观测性、工具链、安全、产品化等 20 个拷问点的后续优化拆解。
> 格式遵循项目任务系统：`- [ ] 任务描述 <!-- files: ... --> <!-- context: ... -->`。
> 执行标注：`review`=需要人工取舍/评审后再做；`order`=必须在前置任务完成后顺序执行；`auto`=可由 Agent 小步直接执行；测试策略为每个子任务优先跑定向测试，阶段性再扩大回归。

## 1. 定位与 MVP 收敛

- [x] 修订 README 中的项目定位：项目对外名称保持 OPC，不再改成新的中文/英文主标题 <!-- files: README.md --> <!-- context: 明确操作系统是远期隐喻，当前能力是软件交付编排层；用户确认“就叫 OPC 就行” --> <!-- decision: 对外名称为 OPC -->
- [x] 在 docs/plan/vision.md 中区分当前能力、实验能力和长期愿景 <!-- files: docs/plan/vision.md --> <!-- context: 避免将 Roadmap 能力描述为已实现能力；能力分级采用严格标准：有代码、有测试、可本地复现才算当前能力 --> <!-- decision: 严格标准 -->
- [x] 定义 MVP 边界：明确 PM → Engineer → QA 是最小可验证交付闭环，并保留 Architect/Ops/Growth 等动态多角色入口 <!-- files: docs/plan/roadmap.md, docs/plan/workflow.md --> <!-- context: 说明输入、输出、验收标准、失败路径；用户确认 MVP 保留多角色，但默认最小闭环仍是 PM/Engineer/QA --> <!-- decision: 保留多角色 -->
- [x] 梳理并降级超出 MVP 的承诺：将未实现的 OS 级能力移动到 Roadmap <!-- files: README.md, docs/plan/roadmap.md --> <!-- context: 包括资源调度、权限隔离、进程管理、多租户等尚未完整实现的能力 --> <!-- order: 依赖 README/API 示例真实性检查；需先确认哪些能力未实现 -->
- [x] 补充 Harness Engineering 方法论定义：说明其与 SDLC、DevOps、Agile 的本质区别 <!-- files: docs/plan/architecture.md, docs/plan/execution.md --> <!-- context: 强调可执行、可验证、可恢复、可观测的 AI 工作流约束系统 --> <!-- review: 需确认方法论表述边界，避免过度营销化 -->

## 2. 文档真实性与示例可运行性

- [x] 检查 README 中所有 API 示例是否与实际代码一致 <!-- files: README.md, src/opc/ --> <!-- context: 移除或修正不存在的 API，例如未实现的 opc.run_as_role() --> <!-- auto: 可直接逐项核对 README 与 src/opc 当前 API -->
- [x] 为 Quickstart 添加最小可运行示例 <!-- files: README.md, examples/ --> <!-- context: 示例应能真实触发 PM → Engineer → QA 或当前可用的最小工作流 --> <!-- order: 依赖 README API 示例核对；新增 examples 需同时补 smoke test -->
- [x] 将 README 中未实现能力统一标注为 Roadmap <!-- files: README.md --> <!-- context: 区分 available、experimental、planned 三类能力；严格标准：有代码、有测试、可本地复现才标 available --> <!-- decision: 严格标准 -->
- [x] 增加文档示例验证测试 <!-- files: tests/ --> <!-- context: 对 README/Quickstart 中的核心示例做 smoke test，防止文档再次漂移 --> <!-- order: 依赖 Quickstart 示例落地后再写测试 -->

## 3. 角色协议与协作可靠性

- [x] 为 PM 输出定义结构化 schema <!-- files: src/opc/schema.py, src/opc/roles.py --> <!-- context: 至少包含 background、goal、scope、non_goals、acceptance_criteria、risks -->
- [x] 为 Engineer 输出定义结构化 schema <!-- files: src/opc/schema.py, src/opc/roles.py --> <!-- context: 至少包含 changed_files、implementation_summary、test_result、known_limits、failure_reason -->
- [x] 为 QA 输出定义结构化 schema <!-- files: src/opc/schema.py, src/opc/roles.py --> <!-- context: 至少包含 pass/fail、checked_items、evidence、defects、next_action -->
- [x] 在工作流流转前校验角色输出 schema <!-- files: src/opc/workflow.py, src/opc/schema.py --> <!-- context: 不符合 schema 时要求当前角色重试或进入人工介入 -->
- [x] 校验 send_to 和 cause_by 字段合法性 <!-- files: src/opc/environment.py, src/opc/schema.py --> <!-- context: 防止消息路由到不存在角色或触发非法状态流转 -->
- [x] 实现动态角色激活策略 <!-- files: src/opc/workflow.py, src/opc/roles.py --> <!-- context: 默认只启用 PM/Engineer/QA，Architect/Ops/Growth 按任务类型或人工选择启用 -->

## 4. 端到端工作流测试

- [x] 添加 PM → Engineer → QA 正常通过的端到端测试 <!-- files: tests/ --> <!-- context: 使用固定输入和 mock LLM response，验证状态流转、产物生成、最终通过 -->
- [x] 添加 QA 打回 Engineer 的端到端测试 <!-- files: tests/ --> <!-- context: 验证 QA fail 后能够回流 Engineer 并再次验收 -->
- [x] 添加 Engineer 失败终止或人工介入测试 <!-- files: tests/ --> <!-- context: 验证实现失败时不会继续进入 QA，也不会无限重试 -->
- [x] 添加工作流中断后恢复测试 <!-- files: tests/ --> <!-- context: 验证从持久化状态恢复后能继续执行且不会产生幽灵任务 -->
- [x] 添加角色输出契约测试 <!-- files: tests/ --> <!-- context: 验证 PM/Engineer/QA 输出缺字段、格式错误时会被拒绝 -->

## 5. Run / Event Store 与状态恢复

- [x] 设计统一 RunStore / ExecutionStore <!-- files: src/opc/ --> <!-- context: 统一管理 workflow state、messages、role outputs、tool calls、tool results、artifacts、errors -->
- [x] 为每次工作流执行生成 run_id <!-- files: src/opc/workflow.py --> <!-- context: 所有状态、消息、工具调用、产物都应关联 run_id -->
- [x] 将工作流状态变化记录为 append-only event log <!-- files: src/opc/ --> <!-- context: 支持复盘、恢复、调试和后续 UI 展示 -->
- [x] 将 Agent 消息缓冲区纳入统一持久化 <!-- files: src/opc/agent.py, src/opc/environment.py --> <!-- context: 避免仅持久化 WorkflowState 导致恢复后上下文缺失 --> <!-- order: 依赖 RunStore 事件模型稳定；先完成消息历史写入再做恢复读取 -->
- [x] 将工具调用和工具结果纳入统一持久化 <!-- files: src/opc/tools/, src/opc/workflow.py --> <!-- context: 恢复和复盘时能看到每次工具输入、输出、失败原因 --> <!-- order: 依赖工具注册协议统一和工具审计日志字段 -->
- [x] 实现中断恢复入口 <!-- files: src/opc/cli.py, src/opc/workflow.py --> <!-- context: P3 做状态恢复：恢复 workflow state、role outputs、messages、tool calls/results，不恢复正在运行的进程 --> <!-- decision: 状态恢复 -->

## 6. 错误处理、返工与循环控制

- [x] 区分 API 失败、工具失败、角色失败、协议失败、QA 失败 <!-- files: src/opc/workflow.py, src/opc/agent.py --> <!-- context: 不同失败类型应有不同处理策略和可观测记录 --> <!-- order: 依赖统一错误类型枚举；完成后再接质量指标和 trace 展示 -->
- [x] 实现 Engineer 失败报告机制 <!-- files: src/opc/workflow.py, src/opc/roles.py --> <!-- context: Engineer 无法完成时输出 failure_reason、blocked_by、suggested_next_step -->
- [x] 实现 QA 不通过后自动回流 Engineer <!-- files: src/opc/workflow.py --> <!-- context: QA defects 应作为 Engineer 下一轮输入 -->
- [x] 增加最大返工次数限制 <!-- files: src/opc/workflow.py, src/opc/config.py --> <!-- context: 超过阈值后进入人工介入，避免死循环 -->
- [x] 增加工具调用最大重试次数 <!-- files: src/opc/tools/, src/opc/config.py --> <!-- context: 区分可重试失败和不可重试失败 --> <!-- order: 依赖工具失败类型分类和工具协议字段 -->
- [x] 增加工作流最大执行轮次限制 <!-- files: src/opc/workflow.py, src/opc/config.py --> <!-- context: 防止角色互相打回导致无限循环 -->

## 7. 可观测性与质量评估

- [x] 记录每个 Agent 的输入、输出、耗时和状态 <!-- files: src/opc/agent.py, src/opc/workflow.py --> <!-- context: 可按 run_id 复盘每个角色的执行链路 -->
- [x] 记录每次工具调用的名称、参数、结果、耗时和错误 <!-- files: src/opc/tools/, src/opc/workflow.py --> <!-- context: 支持工具层审计和失败定位 --> <!-- order: 依赖工具注册协议字段统一；可作为工具持久化前置 -->
- [x] 记录 token 用量和 API 调用次数 <!-- files: src/opc/agent.py, src/opc/workflow.py --> <!-- context: 用于成本评估和预算控制 -->
- [x] 生成结构化 run trace 文件 <!-- files: src/opc/workflow.py, artifacts/ --> <!-- context: 包含 messages、events、tool_calls、metrics、final_status -->
- [x] 增加工作流质量指标 <!-- files: src/opc/workflow.py, tests/ --> <!-- context: 包括 QA 通过率、返工次数、人工介入次数、失败类型分布 --> <!-- order: 依赖失败类型分类和 trace 事件字段稳定 -->
- [x] 在 UI 或历史记录中展示 run trace <!-- files: src/opc/ui.py, src/opc/ --> <!-- context: 如果现有 UI 已支持历史记录，应接入统一 run trace --> <!-- order: 依赖 run trace 字段稳定；UI 展示前需先确认历史记录入口 -->

## 8. 配置、成本与预算控制

- [x] 统一配置优先级 <!-- files: src/opc/config.py, opc.toml, README.md --> <!-- context: 默认配置 → opc.toml → 环境变量 → CLI 参数 → 运行时覆盖；用户确认 CLI 可覆盖配置 --> <!-- decision: CLI 可覆盖 -->
- [x] 拆分 model、roles、tools、workflow、memory、security、cost 配置区块 <!-- files: src/opc/config.py, opc.toml --> <!-- context: 降低配置分散和硬编码风险 --> <!-- order: 依赖配置优先级确认；完成后再做预算控制 -->
- [x] 增加 workflow token 上限配置 <!-- files: src/opc/config.py, src/opc/workflow.py --> <!-- context: P3 仅记录 token 用量和配置项，不强制暂停；后续版本再启用硬限制 --> <!-- decision: 仅观测 -->
- [x] 增加单角色最大 token 和最大调用次数配置 <!-- files: src/opc/config.py, src/opc/agent.py --> <!-- context: P3 仅记录单角色 token/调用次数和配置项，不强制中断；后续版本再启用硬限制 --> <!-- decision: 仅观测 -->
- [x] 增加 API 调用频率限制 <!-- files: src/opc/config.py, src/opc/agent.py --> <!-- context: P3 仅观测 API 调用频率，不做强制中断；CLI 可覆盖配置限制 --> <!-- decision: 仅观测 -->
- [x] 明确敏感信息只能通过环境变量或 secret provider 注入 <!-- files: README.md, docs/plan/architecture.md --> <!-- context: 禁止将 API key 等敏感信息写入 opc.toml --> <!-- auto: 可直接补文档规则，不涉及代码行为 -->

## 9. 工具链完整性与安全

- [x] 统一工具注册协议字段 <!-- files: src/opc/tools/ --> <!-- context: 每个工具需包含 name、description、input_schema、output_schema、permission、side_effect、timeout --> <!-- order: 工具链后续任务的前置项 -->
- [x] 整合 TOOLS_READ_ONLY 和 TOOLS_READ_WRITE 定义 <!-- files: src/opc/tools/, src/opc/agent.py --> <!-- context: 避免工具定义分散且权限语义不一致 --> <!-- order: 依赖工具注册协议字段统一 -->
- [x] 增加 Git status/diff/log 工具 <!-- files: src/opc/tools/ --> <!-- context: 支撑真实软件开发中的变更检查和上下文理解 --> <!-- order: 依赖工具注册协议统一；需纳入权限和审计 -->
- [x] 增加测试执行工具 <!-- files: src/opc/tools/ --> <!-- context: 支持 pytest 或项目配置中的测试命令 --> <!-- order: 依赖工具注册协议统一；需纳入超时和审计 -->
- [x] 增加构建、lint、type check 工具 <!-- files: src/opc/tools/ --> <!-- context: 支持软件交付前的基础验证 --> <!-- order: 依赖工具注册协议统一；需按项目配置决定可用命令 -->
- [x] 为 run_command 增加参数级白名单校验 <!-- files: src/opc/tools/ --> <!-- context: 采用轻限制：保留命令名白名单和基础危险参数识别，主要依赖审计日志追踪 --> <!-- decision: 轻限制 -->
- [x] 限制命令执行工作目录和文件访问范围 <!-- files: src/opc/tools/ --> <!-- context: 默认限制在项目 workspace 内 --> <!-- auto: 可直接增强安全边界并补测试 -->
- [x] 对危险命令增加审计记录 <!-- files: src/opc/tools/, src/opc/workflow.py --> <!-- context: P3 不做人工确认拦截，仅将删除、推送、修改 Git 历史、安装依赖等危险命令写入审计日志 --> <!-- decision: 仅审计 -->
- [x] 增加工具审计日志 <!-- files: src/opc/tools/, src/opc/workflow.py --> <!-- context: 记录谁在何时以什么参数调用了什么工具以及结果 --> <!-- order: 依赖工具注册协议和工具调用 trace 字段 -->

## 10. 知识检索与记忆边界

- [x] 明确 message history 与 RAG 的职责边界 <!-- files: docs/knowledge-retrieval-design.md, docs/plan/architecture.md --> <!-- context: 严格入库：只把稳定项目知识、复盘结论、用户确认的长期决策写入长期记忆；临时日志、推测、失败输出不入库 --> <!-- decision: 严格入库 -->
- [x] 增加长期记忆写入规则 <!-- files: docs/knowledge-retrieval-design.md, src/opc/knowledge/ --> <!-- context: 入库前需要总结、分类、去重、标注来源和时间 --> <!-- order: 依赖 message history 与 RAG 边界确认 -->
- [x] 增加记忆过期和删除机制设计 <!-- files: docs/knowledge-retrieval-design.md, src/opc/knowledge/ --> <!-- context: 避免过期决策、临时日志、未验证猜测污染 RAG --> <!-- review: 需确认默认保留周期和删除触发规则 -->
- [x] 增加代码符号搜索能力 <!-- files: src/opc/knowledge/ --> <!-- context: BM25 只能做文本检索，应补充函数、类、符号级定位能力 --> <!-- auto: 可小步实现 Python 符号索引并补测试 -->
- [x] 增加 import graph 或依赖关系分析能力 <!-- files: src/opc/knowledge/ --> <!-- context: 帮助 Engineer 找到相关文件和潜在影响范围 --> <!-- order: 建议在符号搜索能力之后实现 -->
- [x] 增加测试文件关联能力 <!-- files: src/opc/knowledge/ --> <!-- context: 修改代码时能推荐相关测试文件 --> <!-- order: 建议在符号搜索/import graph 后实现 -->

## 11. 并发、异步与工作流扩展

- [x] 明确 MVP 阶段核心工作流保持同步执行 <!-- files: docs/plan/workflow.md, src/opc/workflow.py --> <!-- context: 核心 PM/Engineer/QA workflow 保持同步；异步只用于测试、构建、索引等长耗时工具任务 --> <!-- decision: 工具异步 -->
- [x] 将长耗时工具执行设计为可选异步任务 <!-- files: src/opc/tools/, src/opc/environment.py --> <!-- context: 异步只用于测试、构建、索引等耗时工具任务；核心角色主链保持同步 --> <!-- decision: 工具异步 -->
- [x] 为异步消息定义顺序、幂等、超时和取消规则 <!-- files: src/opc/environment.py, docs/plan/architecture.md --> <!-- context: 防止消息乱序、重复处理和资源冲突 --> <!-- review: 需确认取消/超时后进入失败还是人工介入 -->
- [x] 从硬编码状态机抽象最小 workflow spec <!-- files: src/opc/workflow.py, src/opc/config.py --> <!-- context: P3 只实现最小声明式 spec，用于表达 QA.pass → Done 和 QA.fail → Engineer，不完整抽象 roles/steps/retry/approval --> <!-- decision: 最小 spec -->
- [x] 支持 QA.pass → Done 和 QA.fail → Engineer 的声明式流转 <!-- files: src/opc/workflow.py, tests/ --> <!-- context: 作为最小 workflow spec 的验证场景；P3 只做该最小声明式流转，不做完整 workflow 引擎 --> <!-- order: 依赖最小 workflow spec 抽象 -->
- [x] 为后续并行任务和子工作流预留接口 <!-- files: docs/plan/architecture.md, src/opc/workflow.py --> <!-- context: 不在 MVP 中复杂实现，但设计上避免封死扩展路径 --> <!-- review: 需确认只写设计文档还是代码接口也落地 -->

## 12. 产品化路线与差异化

- [x] 明确目标用户画像 <!-- files: docs/plan/vision.md, docs/plan/roadmap.md --> <!-- context: 首要目标用户是独立开发者；其他画像作为次级用户或 Roadmap 场景 --> <!-- decision: 独立开发者优先 -->
- [x] 明确与代码补全、IDE Agent、黑盒自动开发工具的差异化 <!-- files: README.md, docs/plan/vision.md --> <!-- context: 不点名竞品；OPC 的核心差异是可控、可审计、可组合的软件交付 Harness --> <!-- decision: 不点名竞品 -->
- [x] 制定 Alpha → Beta → v1 产品化路线图 <!-- files: docs/plan/roadmap.md --> <!-- context: 采用能力递进：Alpha=多角色闭环+trace；Beta=恢复/工具安全/成本观测；v1=自定义 workflow+多项目 --> <!-- decision: 能力递进 -->
- [x] 准备 3-5 个真实样例任务 <!-- files: examples/, docs/ --> <!-- context: 优先覆盖 Bug 修复、功能新增、返工恢复、实现一个轻量级工具 --> <!-- decision: Bug 修复/功能新增/返工恢复/轻量工具 -->
- [x] 为每个样例任务生成可复现 run trace <!-- files: examples/, artifacts/ --> <!-- context: 用真实样例验证项目核心承诺，而不是只靠说明文档 --> <!-- order: 依赖样例任务确认和 run trace 字段稳定 -->

## P3 收尾验收记录

- 2026-05-14 轻量串行验收通过：`tests/test_workflow_spec.py -q`、`test_environment_persists_message_history_and_buffers`、`test_qa_fail_reworks_engineer_once`、workflow run/resume 定向用例均通过。
- 2026-05-14 样例 run trace 复验通过：使用 mock agent 串行验证 `demo-bugfix`、`demo-feature`、`demo-rework`、`demo-tool` 均生成 `run_trace.json`、`run_metrics.json`、`.opc_state.json`；其中 `demo-rework` 覆盖一次 QA 返工。
- 2026-05-14 验收约束：所有命令临时设置 `TEMP/TMP/TMPDIR=E:/Temp/opc`，未跑全量测试，未做大索引。
- 2026-05-14 收尾状态：`docs/new_tools_guide.md` 已按用户要求恢复到本地；本轮仅保留 run trace 指标规整修复与 P3 文档收尾更新。
