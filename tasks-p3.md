# P3: OPC 定位收敛与运行时产品化优化

> 来源：围绕 OPC 当前定位、Harness Engineering、角色协作、可观测性、工具链、安全、产品化等 20 个拷问点的后续优化拆解。
> 格式遵循项目任务系统：`- [ ] 任务描述 <!-- files: ... --> <!-- context: ... -->`。

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
- [ ] 将工具调用和工具结果纳入统一持久化 <!-- files: src/opc/tools/, src/opc/workflow.py --> <!-- context: 恢复和复盘时能看到每次工具输入、输出、失败原因 -->
- [ ] 实现中断恢复入口 <!-- files: src/opc/cli.py, src/opc/workflow.py --> <!-- context: 支持根据 run_id 恢复未完成工作流 -->

## 6. 错误处理、返工与循环控制

- [ ] 区分 API 失败、工具失败、角色失败、协议失败、QA 失败 <!-- files: src/opc/workflow.py, src/opc/agent.py --> <!-- context: 不同失败类型应有不同处理策略和可观测记录 -->
- [x] 实现 Engineer 失败报告机制 <!-- files: src/opc/workflow.py, src/opc/roles.py --> <!-- context: Engineer 无法完成时输出 failure_reason、blocked_by、suggested_next_step -->
- [x] 实现 QA 不通过后自动回流 Engineer <!-- files: src/opc/workflow.py --> <!-- context: QA defects 应作为 Engineer 下一轮输入 -->
- [x] 增加最大返工次数限制 <!-- files: src/opc/workflow.py, src/opc/config.py --> <!-- context: 超过阈值后进入人工介入，避免死循环 -->
- [ ] 增加工具调用最大重试次数 <!-- files: src/opc/tools/, src/opc/config.py --> <!-- context: 区分可重试失败和不可重试失败 -->
- [x] 增加工作流最大执行轮次限制 <!-- files: src/opc/workflow.py, src/opc/config.py --> <!-- context: 防止角色互相打回导致无限循环 -->

## 7. 可观测性与质量评估

- [x] 记录每个 Agent 的输入、输出、耗时和状态 <!-- files: src/opc/agent.py, src/opc/workflow.py --> <!-- context: 可按 run_id 复盘每个角色的执行链路 -->
- [ ] 记录每次工具调用的名称、参数、结果、耗时和错误 <!-- files: src/opc/tools/, src/opc/workflow.py --> <!-- context: 支持工具层审计和失败定位 -->
- [x] 记录 token 用量和 API 调用次数 <!-- files: src/opc/agent.py, src/opc/workflow.py --> <!-- context: 用于成本评估和预算控制 -->
- [x] 生成结构化 run trace 文件 <!-- files: src/opc/workflow.py, artifacts/ --> <!-- context: 包含 messages、events、tool_calls、metrics、final_status -->
- [ ] 增加工作流质量指标 <!-- files: src/opc/workflow.py, tests/ --> <!-- context: 包括 QA 通过率、返工次数、人工介入次数、失败类型分布 -->
- [ ] 在 UI 或历史记录中展示 run trace <!-- files: src/opc/ui.py, src/opc/ --> <!-- context: 如果现有 UI 已支持历史记录，应接入统一 run trace -->

## 8. 配置、成本与预算控制

- [ ] 统一配置优先级 <!-- files: src/opc/config.py, opc.toml, README.md --> <!-- context: 默认配置 → opc.toml → 环境变量 → CLI 参数 → 运行时覆盖 -->
- [ ] 拆分 model、roles、tools、workflow、memory、security、cost 配置区块 <!-- files: src/opc/config.py, opc.toml --> <!-- context: 降低配置分散和硬编码风险 -->
- [ ] 增加 workflow token 上限配置 <!-- files: src/opc/config.py, src/opc/workflow.py --> <!-- context: 超过阈值时暂停并请求人工确认 -->
- [ ] 增加单角色最大 token 和最大调用次数配置 <!-- files: src/opc/config.py, src/opc/agent.py --> <!-- context: 防止单个 Agent 消耗失控 -->
- [ ] 增加 API 调用频率限制 <!-- files: src/opc/config.py, src/opc/agent.py --> <!-- context: 避免短时间重复调用导致成本或限流问题 -->
- [ ] 明确敏感信息只能通过环境变量或 secret provider 注入 <!-- files: README.md, docs/plan/architecture.md --> <!-- context: 禁止将 API key 等敏感信息写入 opc.toml -->

## 9. 工具链完整性与安全

- [ ] 统一工具注册协议字段 <!-- files: src/opc/tools/ --> <!-- context: 每个工具需包含 name、description、input_schema、output_schema、permission、side_effect、timeout -->
- [ ] 整合 TOOLS_READ_ONLY 和 TOOLS_READ_WRITE 定义 <!-- files: src/opc/tools/, src/opc/agent.py --> <!-- context: 避免工具定义分散且权限语义不一致 -->
- [ ] 增加 Git status/diff/log 工具 <!-- files: src/opc/tools/ --> <!-- context: 支撑真实软件开发中的变更检查和上下文理解 -->
- [ ] 增加测试执行工具 <!-- files: src/opc/tools/ --> <!-- context: 支持 pytest 或项目配置中的测试命令 -->
- [ ] 增加构建、lint、type check 工具 <!-- files: src/opc/tools/ --> <!-- context: 支持软件交付前的基础验证 -->
- [ ] 为 run_command 增加参数级白名单校验 <!-- files: src/opc/tools/ --> <!-- context: 不能只校验命令名，还要限制危险参数和 shell 注入 -->
- [ ] 限制命令执行工作目录和文件访问范围 <!-- files: src/opc/tools/ --> <!-- context: 默认限制在项目 workspace 内 -->
- [ ] 对危险命令增加人工确认机制 <!-- files: src/opc/tools/, src/opc/workflow.py --> <!-- context: 删除、推送、修改 Git 历史、安装依赖等操作需要确认 -->
- [ ] 增加工具审计日志 <!-- files: src/opc/tools/, src/opc/workflow.py --> <!-- context: 记录谁在何时以什么参数调用了什么工具以及结果 -->

## 10. 知识检索与记忆边界

- [ ] 明确 message history 与 RAG 的职责边界 <!-- files: docs/knowledge-retrieval-design.md, docs/plan/architecture.md --> <!-- context: 当前任务过程留在短期上下文，稳定项目知识和复盘进入长期记忆 -->
- [ ] 增加长期记忆写入规则 <!-- files: docs/knowledge-retrieval-design.md, src/opc/knowledge/ --> <!-- context: 入库前需要总结、分类、去重、标注来源和时间 -->
- [ ] 增加记忆过期和删除机制设计 <!-- files: docs/knowledge-retrieval-design.md, src/opc/knowledge/ --> <!-- context: 避免过期决策、临时日志、未验证猜测污染 RAG -->
- [ ] 增加代码符号搜索能力 <!-- files: src/opc/knowledge/ --> <!-- context: BM25 只能做文本检索，应补充函数、类、符号级定位能力 -->
- [ ] 增加 import graph 或依赖关系分析能力 <!-- files: src/opc/knowledge/ --> <!-- context: 帮助 Engineer 找到相关文件和潜在影响范围 -->
- [ ] 增加测试文件关联能力 <!-- files: src/opc/knowledge/ --> <!-- context: 修改代码时能推荐相关测试文件 -->

## 11. 并发、异步与工作流扩展

- [ ] 明确 MVP 阶段核心工作流保持同步执行 <!-- files: docs/plan/workflow.md, src/opc/workflow.py --> <!-- context: 避免在协议、恢复、隔离不足时过早引入多 Agent 并发 -->
- [ ] 将长耗时工具执行设计为可选异步任务 <!-- files: src/opc/tools/, src/opc/environment.py --> <!-- context: 异步只用于测试、构建、索引等耗时操作 -->
- [ ] 为异步消息定义顺序、幂等、超时和取消规则 <!-- files: src/opc/environment.py, docs/plan/architecture.md --> <!-- context: 防止消息乱序、重复处理和资源冲突 -->
- [ ] 从硬编码状态机抽象 workflow spec <!-- files: src/opc/workflow.py, src/opc/config.py --> <!-- context: 支持 roles、steps、transitions、conditions、retry_policy、approval_gates -->
- [ ] 支持 QA.pass → Done 和 QA.fail → Engineer 的声明式流转 <!-- files: src/opc/workflow.py, tests/ --> <!-- context: 作为声明式工作流的最小验证场景 -->
- [ ] 为后续并行任务和子工作流预留接口 <!-- files: docs/plan/architecture.md, src/opc/workflow.py --> <!-- context: 不在 MVP 中复杂实现，但设计上避免封死扩展路径 -->

## 12. 产品化路线与差异化

- [ ] 明确目标用户画像 <!-- files: docs/plan/vision.md, docs/plan/roadmap.md --> <!-- context: 至少区分 solo founder、独立开发者、小团队技术负责人、Agent infra 研究者 -->
- [ ] 明确与 Cursor、Copilot、Devin 的差异化 <!-- files: README.md, docs/plan/vision.md --> <!-- context: OPC 的核心差异是可控、可审计、可组合的软件交付 Harness -->
- [ ] 制定 Alpha → Beta → v1 产品化路线图 <!-- files: docs/plan/roadmap.md --> <!-- context: Alpha 固定闭环，Beta 可观测/恢复/安全/成本，v1 自定义 workflow 和多项目 -->
- [ ] 准备 3-5 个真实样例任务 <!-- files: examples/, docs/ --> <!-- context: 覆盖文档修改、bug 修复、功能新增、QA 打回、失败恢复 -->
- [ ] 为每个样例任务生成可复现 run trace <!-- files: examples/, artifacts/ --> <!-- context: 用真实样例验证项目核心承诺，而不是只靠说明文档 -->
