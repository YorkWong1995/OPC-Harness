# P8: OPC 功能增强细颗粒度任务拆分

> 来源：tasks-p7.md。
> 目标：把 P7 的能力补齐方向拆成更小、可执行、可验收的任务。
> 拆分原则：一条任务尽量只覆盖一个文件类型、一个流程步骤或一个可验收目标。
> 格式遵循项目任务系统：`- [ ] 任务描述 <!-- files: ... --> <!-- context: ... -->`。
> 执行标注：`review`=需要人工取舍/评审后再做；`order`=必须在前置任务完成后顺序执行；`auto`=可由 Agent 小步直接执行；`decision`=已确认的决策。
> 测试策略：优先跑定向测试或文档检查，避免全量测试影响本机性能。

## 1. P0 - Coding / QA / Cost Skills

- [x] 定义 bugfix skill 基础说明 <!-- files: .claude/skills/bugfix/SKILL.md --> <!-- context: 责任角色=Engineer/QA；输入=tasks-p7.md 中 bugfix skill 要求、现有 task-spec/acceptance-check skill 格式；输出=bugfix skill 的 name、description、目标、适用场景；依赖关系=无；完成标准=SKILL.md 存在且说明 bugfix 只做缺陷定位、最小修复和定向验证 --> <!-- auto: 新增单个 skill 文档 -->
- [x] 补充 bugfix skill 执行流程 <!-- files: .claude/skills/bugfix/SKILL.md --> <!-- context: 责任角色=Engineer/QA；输入=缺陷描述、复现路径、预期行为、相关文件；输出=定位→根因→最小修复→验证→验收证据的步骤；依赖关系=依赖 bugfix skill 基础说明；完成标准=执行规则明确禁止超范围重构，并要求输出根因和验证证据 --> <!-- order: 依赖 bugfix 基础说明 -->
- [x] 补充 bugfix skill 示例与验收 <!-- files: .claude/skills/bugfix/SKILL.md --> <!-- context: 责任角色=QA；输入=bugfix 执行流程；输出=用户调用示例、输出骨架、验收标准；依赖关系=依赖 bugfix 执行流程；完成标准=至少包含 2 个调用示例和 1 个可检查输出骨架 --> <!-- order: 依赖 bugfix 执行流程 -->

- [x] 定义 test-spec skill 基础说明 <!-- files: .claude/skills/test-spec/SKILL.md --> <!-- context: 责任角色=QA/Engineer；输入=tasks-p7.md 中 test-spec 要求、现有 standards.md 任务/验收字段；输出=test-spec skill 的 name、description、目标、适用场景；依赖关系=无；完成标准=SKILL.md 存在且说明该 skill 把 PRD、bug 或任务描述转成测试点 --> <!-- auto: 新增单个 skill 文档 -->
- [x] 补充 test-spec 测试维度模板 <!-- files: .claude/skills/test-spec/SKILL.md --> <!-- context: 责任角色=QA；输入=PRD、bug、任务描述、验收标准；输出=正常路径、失败路径、边界条件、回归风险、验证命令模板；依赖关系=依赖 test-spec 基础说明；完成标准=模板覆盖至少 5 类测试维度，且每类都有输出要求 --> <!-- order: 依赖 test-spec 基础说明 -->
- [x] 补充 test-spec 示例与验收 <!-- files: .claude/skills/test-spec/SKILL.md --> <!-- context: 责任角色=QA；输入=test-spec 测试维度模板；输出=调用示例、输出骨架、验收标准；依赖关系=依赖测试维度模板；完成标准=至少包含从需求生成测试点和从 bug 生成回归测试两类示例 --> <!-- order: 依赖 test-spec 测试维度模板 -->

- [x] 定义 implementation-check skill 基础说明 <!-- files: .claude/skills/implementation-check/SKILL.md --> <!-- context: 责任角色=QA/Engineer；输入=task-spec、PRD、架构约束、pending diff；输出=implementation-check skill 的 name、description、目标、适用场景；依赖关系=现有 task-spec 与 acceptance-check；完成标准=SKILL.md 存在且说明该 skill 是 QA 前实现自检，不替代 QA 验收 --> <!-- order: 依赖 task-spec 与 acceptance-check 已存在 -->
- [x] 补充 implementation-check 检查清单 <!-- files: .claude/skills/implementation-check/SKILL.md --> <!-- context: 责任角色=QA/Engineer；输入=任务定义、实现 diff、验证结果；输出=范围一致性、文件变更、测试证据、已知限制、风险项检查清单；依赖关系=依赖 implementation-check 基础说明；完成标准=检查清单能输出“建议进入 QA / 不建议进入 QA”的明确结论 --> <!-- order: 依赖 implementation-check 基础说明 -->
- [x] 补充 implementation-check 示例与验收 <!-- files: .claude/skills/implementation-check/SKILL.md --> <!-- context: 责任角色=QA；输入=implementation-check 检查清单；输出=调用示例、输出骨架、验收标准；依赖关系=依赖检查清单；完成标准=示例覆盖“实现符合任务”和“实现偏离任务”两种结果 --> <!-- order: 依赖 implementation-check 检查清单 -->

- [x] 定义 token-report skill 基础说明 <!-- files: .claude/skills/token-report/SKILL.md --> <!-- context: 责任角色=Ops/QA；输入=run_metrics.json、run_trace.json、run_events.jsonl；输出=token-report skill 的 name、description、目标、适用场景；依赖关系=现有 run metrics；完成标准=SKILL.md 存在且说明只读 artifacts，不重新调用模型 --> <!-- auto: 新增单个 skill 文档 -->
- [x] 补充 token-report 输出字段模板 <!-- files: .claude/skills/token-report/SKILL.md --> <!-- context: 责任角色=Ops；输入=单次 run 的 metrics；输出=总 input/output tokens、api_calls、duration、分阶段消耗、最高消耗阶段、异常项、优化建议；依赖关系=依赖 token-report 基础说明；完成标准=输出字段能直接对应 run_metrics.json 的已有或计划字段 --> <!-- order: 依赖 token-report 基础说明 -->
- [x] 补充 token-report 示例与验收 <!-- files: .claude/skills/token-report/SKILL.md --> <!-- context: 责任角色=QA/Ops；输入=token-report 输出字段模板；输出=调用示例、报告骨架、验收标准；依赖关系=依赖输出字段模板；完成标准=示例覆盖 latest run 和指定 artifacts 路径两种用法 --> <!-- order: 依赖 token-report 输出字段模板 -->

## 2. P0 - Token / Model / Cost 运行指标

- [x] 设计 run_metrics 的 cost 字段结构 <!-- files: docs/plan/workflow.md, src/opc/workflow.py --> <!-- context: 责任角色=Architect/Ops；输入=现有 run_metrics.json、stage_logs、token-report 字段需求；输出=model、input_tokens、output_tokens、estimated_cost、currency、pricing_source 的字段说明；依赖关系=依赖 token-report 输出字段模板；完成标准=字段结构能支持单阶段和总计两级统计 --> <!-- order: 依赖 token-report 字段模板 -->
- [x] 在 workflow 阶段日志中记录 model 字段 <!-- files: src/opc/workflow.py, tests/ --> <!-- context: 责任角色=Engineer；输入=Agent model、现有 stage_logs；输出=每个 stage log 记录 model；依赖关系=依赖 cost 字段设计；完成标准=run_metrics.json 的每个阶段可看到 model，缺省 model 时有兼容值 --> <!-- order: 依赖 cost 字段设计 -->
- [x] 在 workflow 阶段日志中记录 token 字段兼容逻辑 <!-- files: src/opc/workflow.py, tests/ --> <!-- context: 责任角色=Engineer/QA；输入=Agent usage、现有 input_tokens/output_tokens；输出=缺 usage 时安全落空，存在 usage 时写入 token；依赖关系=依赖 model 字段记录；完成标准=测试覆盖 usage 存在和缺失两种情况 --> <!-- order: 依赖 model 字段记录 -->
- [x] 增加 cost 估算配置 <!-- files: src/opc/config.py, opc.example.toml, tests/ --> <!-- context: 责任角色=Ops/Engineer；输入=模型价格、currency、是否启用估算；输出=CostConfig 或等价配置；依赖关系=依赖 cost 字段设计；完成标准=配置有默认值，用户可关闭估算或覆盖模型价格 --> <!-- review: 需确认价格来源和默认模型价格策略 -->
- [x] 生成 run_metrics cost 汇总 <!-- files: src/opc/workflow.py, tests/ --> <!-- context: 责任角色=Engineer/Ops；输入=阶段 token、model、cost 配置；输出=每阶段 estimated_cost 与 totals.estimated_cost；依赖关系=依赖 token 字段兼容逻辑和 cost 配置；完成标准=run_metrics.json 同时包含阶段成本和总成本，测试覆盖未知模型价格时的行为 --> <!-- order: 依赖 token 字段与 cost 配置 -->

## 3. P1 - Review / Release Skills

- [x] 定义 review skill 基础说明 <!-- files: .claude/skills/review/SKILL.md --> <!-- context: 责任角色=QA/Architect；输入=pending diff、PR、指定文件、任务结果；输出=review skill 的 name、description、目标、适用场景；依赖关系=无；完成标准=SKILL.md 存在且说明该 skill 是只读评审，不直接修改代码 --> <!-- auto: 新增单个 skill 文档 -->
- [x] 补充 review 输出分类规则 <!-- files: .claude/skills/review/SKILL.md --> <!-- context: 责任角色=QA/Architect；输入=diff 或文件内容；输出=阻塞问题、非阻塞建议、风险判断、通过/不通过/需调整结论；依赖关系=依赖 review 基础说明；完成标准=规则明确区分 blocking 与 non-blocking，要求证据引用文件路径 --> <!-- order: 依赖 review 基础说明 -->
- [x] 补充 review 示例与验收 <!-- files: .claude/skills/review/SKILL.md --> <!-- context: 责任角色=QA；输入=review 输出分类规则；输出=调用示例、输出骨架、验收标准；依赖关系=依赖输出分类规则；完成标准=示例覆盖 pass 和 needs-work 两种结论 --> <!-- order: 依赖 review 输出分类规则 -->

- [x] 定义 release-check skill 基础说明 <!-- files: .claude/skills/release-check/SKILL.md --> <!-- context: 责任角色=Ops；输入=实现结果、验收结果、运行环境、发布对象；输出=release-check skill 的 name、description、目标、适用场景；依赖关系=无；完成标准=SKILL.md 存在且说明该 skill 只做发布建议，不执行真实发布 --> <!-- auto: 新增单个 skill 文档 -->
- [x] 补充 release-check 发布检查模板 <!-- files: .claude/skills/release-check/SKILL.md --> <!-- context: 责任角色=Ops；输入=发布对象、验证结果、环境信息；输出=发布前检查项、运行验证方式、监控关注点、回滚条件、发布结论；依赖关系=依赖 release-check 基础说明；完成标准=模板与 standards.md 发布检查字段一致 --> <!-- order: 依赖 release-check 基础说明 -->
- [x] 补充 release-check 示例与验收 <!-- files: .claude/skills/release-check/SKILL.md --> <!-- context: 责任角色=QA/Ops；输入=发布检查模板；输出=调用示例、输出骨架、验收标准；依赖关系=依赖发布检查模板；完成标准=示例覆盖“可发布”和“需要补充信息”两种结论 --> <!-- order: 依赖 release-check 发布检查模板 -->

## 4. P1 - Workflow Pack / Manifest

- [x] 定义 workflow pack 目录结构 <!-- files: docs/workflow-packs/README.md --> <!-- context: 责任角色=Architect/PM；输入=docs/plan/workflow.md 中 Workflow Pack 规范；输出=docs/workflow-packs/ 目录说明；依赖关系=无；完成标准=README 说明 pack 文件命名、字段、适用范围和维护规则 --> <!-- review: 新目录结构确认 -->
- [x] 定义 workflow pack manifest 字段模板 <!-- files: docs/workflow-packs/manifest-template.md --> <!-- context: 责任角色=Architect；输入=standards.md 中 Manifest 字段；输出=id、kind、owner_roles、inputs、outputs、permissions、acceptance、trace 模板；依赖关系=依赖目录结构；完成标准=模板可被后续 pack 复制使用 --> <!-- order: 依赖 workflow pack 目录结构 -->
- [x] 新增 bugfix workflow pack 样板 <!-- files: docs/workflow-packs/bugfix.md --> <!-- context: 责任角色=Architect/Engineer/QA；输入=bugfix skill、manifest 模板；输出=bugfix pack 的适用场景、角色边界、权限边界、验收方式；依赖关系=依赖 manifest 模板和 bugfix skill；完成标准=bugfix pack 可说明何时走 runtime workflow，何时只用 skill --> <!-- order: 依赖 manifest 模板和 bugfix skill -->
- [x] 新增 review workflow pack 样板 <!-- files: docs/workflow-packs/review.md --> <!-- context: 责任角色=QA/Architect；输入=review skill、manifest 模板；输出=review pack 的只读评审边界；依赖关系=依赖 manifest 模板和 review skill；完成标准=review pack 明确默认只读，若需写代码则转 bugfix pack --> <!-- order: 依赖 manifest 模板和 review skill -->
- [x] 新增 docs-update workflow pack 样板 <!-- files: docs/workflow-packs/docs-update.md --> <!-- context: 责任角色=PM/QA；输入=文档更新场景、manifest 模板；输出=docs-update pack 的输入、输出、权限、验收；依赖关系=依赖 manifest 模板；完成标准=docs-update pack 明确文档链接/索引检查作为验收项 --> <!-- order: 依赖 manifest 模板 -->
- [x] 新增 release-check workflow pack 样板 <!-- files: docs/workflow-packs/release-check.md --> <!-- context: 责任角色=Ops/QA；输入=release-check skill、manifest 模板；输出=release-check pack 的发布前检查边界；依赖关系=依赖 manifest 模板和 release-check skill；完成标准=pack 明确不执行真实发布，只输出检查结论和回滚条件 --> <!-- order: 依赖 manifest 模板和 release-check skill -->

## 5. P1 - 可选角色启用规则

- [x] 梳理可选角色触发词表 <!-- files: src/opc/roles.py, docs/plan/workflow.md --> <!-- context: 责任角色=PM/Architect；输入=OPTIONAL_ROLE_KEYWORDS、ROLE_CLASSIFIER_PROMPT、现有文档；输出=Architect/Ops/Growth 的触发词和语义说明；依赖关系=无；完成标准=文档和代码中的触发语义一致 --> <!-- auto: 文档与代码核对 -->
- [x] 补充手动角色开关说明 <!-- files: docs/plan/workflow.md, README.md --> <!-- context: 责任角色=PM；输入=CLI --with-architect/--with-ops/--with-growth/--skip-architect/--ceo-review；输出=用户何时手动打开或关闭可选角色的说明；依赖关系=依赖触发词表梳理；完成标准=README 或 workflow 文档能解释自动识别与手动覆盖的关系 --> <!-- order: 依赖触发词表梳理 -->
- [ ] 增加可选角色分类测试 <!-- files: tests/test_roles.py, src/opc/roles.py --> <!-- context: 责任角色=QA/Engineer；输入=典型 architect/ops/growth/无可选角色任务描述；输出=分类或关键词兜底测试；依赖关系=依赖触发词表梳理；完成标准=测试覆盖 4 类任务描述，避免明显误触或漏触 --> <!-- order: 依赖触发词表梳理 -->

## 6. P1 - Scripts 目录与入口整理

- [ ] 盘点根目录脚本用途 <!-- files: README.md, docs/DOCS_STRUCTURE.md, run_opc.py, run_tasks.py, pre_upload_check.sh, upload_to_github.sh --> <!-- context: 责任角色=Ops/PM；输入=当前根目录脚本；输出=脚本用途、是否保留、是否移动到 scripts/ 的决策记录；依赖关系=无；完成标准=每个脚本都有保留/迁移/废弃结论 --> <!-- review: 文件移动前先确认策略 -->
- [ ] 创建 scripts 目录说明 <!-- files: scripts/README.md --> <!-- context: 责任角色=Ops；输入=脚本盘点结论；输出=scripts/ 分类、命名和使用规则；依赖关系=依赖脚本用途盘点；完成标准=scripts/README.md 说明 run/check/review/cost/upload 的入口分类 --> <!-- order: 依赖脚本盘点 -->
- [ ] 迁移或包装 run 类脚本入口 <!-- files: scripts/, run_opc.py, run_tasks.py --> <!-- context: 责任角色=Engineer/Ops；输入=run_opc.py、run_tasks.py、scripts 目录规则；输出=scripts/ 下 run 相关入口或包装脚本；依赖关系=依赖 scripts 目录说明；完成标准=旧入口是否保留有明确策略，新入口可执行或有说明 --> <!-- review: 涉及入口兼容策略 -->
- [ ] 迁移或包装 check/upload 类脚本入口 <!-- files: scripts/, pre_upload_check.sh, upload_to_github.sh --> <!-- context: 责任角色=Ops；输入=pre_upload_check.sh、upload_to_github.sh、scripts 目录规则；输出=scripts/ 下 check/upload 相关入口或包装脚本；依赖关系=依赖 scripts 目录说明；完成标准=上传前检查与上传入口位置清晰，危险操作仍需人工确认 --> <!-- review: 涉及 git add/push 脚本安全边界 -->

## 7. P1 - 项目级可复用 Agent 资产层

- [ ] 定义 agent 资产格式 <!-- files: .claude/agents/README.md, docs/plan/architecture.md --> <!-- context: 责任角色=Architect；输入=runtime agent、roles.py、skills、workflow pack；输出=agent 资产字段、边界、与 skill/workflow 的区别；依赖关系=依赖 workflow pack 目录结构；完成标准=文档说明 agent 资产不是 runtime 实现，而是可复用角色/任务配置 --> <!-- review: 需确认资产格式 -->
- [ ] 新增 PM agent 资产样板 <!-- files: .claude/agents/pm.md --> <!-- context: 责任角色=PM；输入=roles.py 中 PM prompt、roles.md PM 职责；输出=PM agent 资产样板；依赖关系=依赖 agent 资产格式；完成标准=样板包含用途、输入、输出、工具边界和禁止事项 --> <!-- order: 依赖 agent 资产格式 -->
- [ ] 新增 Engineer agent 资产样板 <!-- files: .claude/agents/engineer.md --> <!-- context: 责任角色=Engineer；输入=roles.py 中 Engineer prompt、roles.md Engineer 职责；输出=Engineer agent 资产样板；依赖关系=依赖 agent 资产格式；完成标准=样板说明可写代码但必须最小实现和可验证 --> <!-- order: 依赖 agent 资产格式 -->
- [ ] 新增 QA agent 资产样板 <!-- files: .claude/agents/qa.md --> <!-- context: 责任角色=QA；输入=roles.py 中 QA prompt、roles.md QA 职责；输出=QA agent 资产样板；依赖关系=依赖 agent 资产格式；完成标准=样板说明只读验收、证据要求和 pass/fail 结论 --> <!-- order: 依赖 agent 资产格式 -->

## 8. P2 - 知识复用与 Memory 边界

- [ ] 设计任务结果知识回流规则 <!-- files: docs/knowledge-retrieval-design.md, docs/plan/workflow.md --> <!-- context: 责任角色=Architect/PM；输入=任务结果、验证证据、复盘结论、RAG、memory 边界；输出=哪些内容可回流、哪些必须人工确认、哪些禁止写入；依赖关系=现有 memory 与 RAG 边界；完成标准=规则明确 run artifact、memory、索引三者差异 --> <!-- review: 避免过度自动写 memory -->
- [ ] 实现 memory 写入前的复盘内容筛选 <!-- files: src/opc/memory.py, src/opc/workflow.py, tests/ --> <!-- context: 责任角色=Engineer/QA；输入=知识回流规则、复盘产物、memory write policy；输出=复盘内容候选筛选逻辑；依赖关系=依赖知识回流规则；完成标准=只有经确认的长期偏好/项目决策/外部引用能进入 memory，测试覆盖临时 run 状态不写入 --> <!-- order: 依赖知识回流规则 -->
- [ ] 增强检索来源追踪说明 <!-- files: docs/knowledge-retrieval-design.md, src/opc/workflow.py, tests/ --> <!-- context: 责任角色=QA/Engineer；输入=RAG source attribution、context_sources、memory id/source；输出=检索来源记录和文档说明；依赖关系=依赖知识回流规则；完成标准=回答或 Context Pack 中可追踪来源，当前文件事实优先于历史 memory --> <!-- order: 依赖知识回流规则 -->

## 9. P2 - Cost 趋势分析 CLI

- [ ] 设计 cost trend 命令输出格式 <!-- files: docs/plan/workflow.md, README.md --> <!-- context: 责任角色=Ops/PM；输入=多次 run 的 run_metrics.json、token-report 输出；输出=最近 N 次 run 的 cost trend 输出字段和示例；依赖关系=依赖 cost 指标记录；完成标准=格式包含按 run、阶段、角色聚合的 token/cost/duration --> <!-- order: 依赖 cost 指标记录 -->
- [ ] 实现读取多次 run metrics 的聚合函数 <!-- files: src/opc/run_store.py, tests/ --> <!-- context: 责任角色=Engineer/QA；输入=artifacts 下多个 run_metrics.json；输出=按 run_id 聚合 token/cost/duration 的函数；依赖关系=依赖 cost trend 输出格式；完成标准=测试覆盖缺失 metrics、旧 metrics、多个 run 三种情况 --> <!-- order: 依赖 cost trend 输出格式 -->
- [ ] 增加 cost trend CLI 入口 <!-- files: src/opc/cli.py, tests/ --> <!-- context: 责任角色=Engineer/Ops；输入=聚合函数、CLI runs/trace 现有命令；输出=opc runs cost 或等价只读命令；依赖关系=依赖 metrics 聚合函数；完成标准=用户可查看最近 N 次 run 的 token/cost 趋势，不调用模型或工具 --> <!-- order: 依赖 metrics 聚合函数 -->

## 10. P2 - 质量门禁与索引

- [ ] 定义实现自检到 QA 的门禁顺序 <!-- files: docs/plan/workflow.md --> <!-- context: 责任角色=QA/PM；输入=implementation-check、acceptance-check、QA 输出；输出=实现完成后进入 QA 前的检查顺序和失败路径；依赖关系=依赖 implementation-check skill；完成标准=文档明确自检失败时不进入 QA，转回 Engineer 修正 --> <!-- order: 依赖 implementation-check skill -->
- [ ] 定义发布类任务的发布前门禁 <!-- files: docs/plan/workflow.md --> <!-- context: 责任角色=Ops/QA；输入=release-check skill、QA 通过结果、运行环境；输出=发布前检查顺序、回滚条件、人工确认节点；依赖关系=依赖 release-check skill；完成标准=发布类任务必须有回滚条件和运行验证方式 --> <!-- order: 依赖 release-check skill -->
- [ ] 建立 skills 索引文档 <!-- files: README.md, docs/DOCS_STRUCTURE.md, .claude/skills/ --> <!-- context: 责任角色=PM/QA；输入=现有和新增 skills；输出=skills 列表、用途、调用方式、适用场景；依赖关系=依赖新增 skills 完成；完成标准=用户能从 README 或 DOCS_STRUCTURE 找到每个 skill --> <!-- order: 依赖新增 skills 完成 -->
- [ ] 建立 workflow packs 索引文档 <!-- files: docs/DOCS_STRUCTURE.md, docs/workflow-packs/README.md --> <!-- context: 责任角色=PM/QA；输入=workflow pack 样板；输出=pack 列表、适用场景、边界说明；依赖关系=依赖 workflow pack 样板完成；完成标准=用户能快速判断 bugfix/review/docs-update/release-check pack 何时使用 --> <!-- order: 依赖 workflow pack 样板完成 -->
- [ ] 建立 scripts 索引文档 <!-- files: README.md, docs/DOCS_STRUCTURE.md, scripts/README.md --> <!-- context: 责任角色=Ops/QA；输入=scripts 目录说明和脚本入口；输出=脚本列表、用途、风险说明；依赖关系=依赖 scripts 入口整理完成；完成标准=用户能知道每个脚本是否只读、是否写入、是否触发 git 操作 --> <!-- order: 依赖 scripts 入口整理 -->
- [ ] 建立 agent 资产索引文档 <!-- files: docs/DOCS_STRUCTURE.md, .claude/agents/README.md --> <!-- context: 责任角色=Architect/QA；输入=agent 资产样板；输出=agent 资产列表、用途、与 runtime agent 的区别；依赖关系=依赖 agent 资产样板完成；完成标准=用户能区分 skill、agent 资产、runtime agent 和 workflow 的边界 --> <!-- order: 依赖 agent 资产样板 -->

## 11. 阶段验收

- [ ] P8 skills 验收 <!-- files: .claude/skills/, tasks-p8.md --> <!-- context: 责任角色=QA；输入=P8 新增所有 skill 文档；输出=skills 验收记录；依赖关系=依赖新增 skills 完成；完成标准=bugfix/test-spec/implementation-check/token-report/review/release-check 均存在 SKILL.md，且每个包含用法、执行规则、输出骨架和验收标准 --> <!-- order: 依赖所有新增 skill 完成 -->
- [ ] P8 runtime metrics 验收 <!-- files: src/opc/workflow.py, src/opc/run_store.py, src/opc/config.py, tests/ --> <!-- context: 责任角色=QA/Ops；输入=token/model/cost 指标任务；输出=metrics 验收记录；依赖关系=依赖 token/model/cost 指标完成；完成标准=run_metrics.json 可表达分阶段 model、token、cost 和总计，缺 usage 信息时兼容 --> <!-- order: 依赖 runtime metrics 任务完成 -->
- [ ] P8 资产层验收 <!-- files: docs/workflow-packs/, scripts/, .claude/agents/, docs/DOCS_STRUCTURE.md --> <!-- context: 责任角色=QA/Architect；输入=workflow pack、scripts、agent 资产和索引；输出=资产层验收记录；依赖关系=依赖 P1/P2 资产任务完成；完成标准=workflow packs、scripts、agents 都有 README 或索引，样板可找到且边界清楚 --> <!-- order: 依赖资产层任务完成 -->
- [ ] P8 总体验收 <!-- files: tasks-p8.md, docs/plan/roadmap.md, tasks-p7.md --> <!-- context: 责任角色=QA/Ops；输入=P8 所有产物和 P7 路线图；输出=总体验收记录；依赖关系=依赖前述 P8 验收完成；完成标准=P8 任务能覆盖 P7 全部能力方向，且每个能力方向至少有一个可检查产物或测试证据 --> <!-- order: 依赖 P8 前述验收完成 -->
