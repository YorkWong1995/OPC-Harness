# Beta 阶段完成任务清单

> 基于 README.md 产品化路线图，Beta 阶段定义为：**中断恢复 + 工具安全审计 + 成本观测 + 符号搜索**。
> 本文档列出 Beta 阶段验收前必须完成的任务，按优先级和依赖关系组织。

## 验收标准

Beta 阶段完成需满足：

1. **安全性**：工具调用可审计、成本硬限制生效、路径遍历防护到位
2. **可用性**：WorkflowSpec 完全驱动工作流、交互模式重试延迟合理
3. **可维护性**：核心模块职责清晰、测试覆盖 >80%
4. **文档一致性**：Harness 资产无失效引用、规则可执行

---

## P0 - 安全与可用性红线（必须立即修复）

### 工具安全审计

- [x] Agent 工具循环添加终止保护 <!-- files: src/opc/agent.py:153 --> <!-- context: while True 循环无迭代上限，失控时持续消耗 API 额度；添加 max_tool_rounds=15 参数和超限检测 --> <!-- auto -->
- [x] 修复路径遍历检查绕过漏洞 <!-- files: src/opc/agent.py:758-764 --> <!-- context: startswith 字符串比较不安全；改用 Path.is_relative_to() 方法 --> <!-- auto -->
- [x] 实现成本控制硬限制 <!-- files: src/opc/workflow.py:337-356, src/opc/config.py --> <!-- context: 当前只打印警告不中断执行；添加 hard_limit 配置和强制中断逻辑 --> <!-- auto -->
- [x] 修复交互模式 API 重试延迟 <!-- files: src/opc/agent.py:22 --> <!-- context: 30 分钟基础间隔对 CLI 交互场景不可用；区分 interactive/batch 模式，interactive 改为 10 秒 --> <!-- auto -->

### 测试覆盖

- [x] 添加 P0 安全修复的测试用例 <!-- files: tests/test_path_safety.py, tests/test_cost_hard_limit.py, tests/test_retry_mode.py --> <!-- context: 所有 P0 修复必须有对应测试；验证工具循环终止、路径遍历拦截、成本硬限制触发、重试延迟合理 --> <!-- order: 依赖 P0 修复完成 -->

---

## P1 - 核心功能缺陷（影响系统可用性）

### WorkflowSpec 完整生效

- [x] 让 WorkflowSpec 驱动状态流转 <!-- files: src/opc/workflow.py:595-612 --> <!-- context: 声明式 spec 存在但不生效，文档与实现不符；从 spec 读取 stage handler 和 next_state 逻辑 --> <!-- review: 需确认 spec 格式是否需调整 -->
- [x] 添加 WorkflowSpec 端到端集成测试 <!-- files: tests/test_workflow_spec_integration.py --> <!-- context: 验证自定义 spec 能正确驱动工作流执行；测试 stage 顺序、条件跳转、并行执行 --> <!-- order: 依赖 WorkflowSpec 驱动完成 -->

### 异步上下文兼容

- [x] 修复 asyncio.run() 与同步代码混用 <!-- files: src/opc/workflow.py:635 --> <!-- context: 同步 run() 内嵌 asyncio.run()，未来 Web UI 调用会抛 RuntimeError；推荐方案 A：全异步化 HarnessWorkflow.run() --> <!-- review: 需确认是否影响现有 CLI 调用 -->
- [x] 添加异步上下文调用测试 <!-- files: tests/test_workflow_async.py --> <!-- context: 验证 HarnessWorkflow 可在 async 上下文（如 FastAPI）中调用 --> <!-- order: 依赖异步化完成 -->

### QA rework 循环优化

- [x] QA rework 改用循环实现 <!-- files: src/opc/workflow.py:890 --> <!-- context: 当前用递归实现，隐式状态不变量脆弱；改为 while 循环显式管理 rework_attempts --> <!-- auto -->
- [x] 添加 QA rework 循环测试 <!-- files: tests/test_qa_rework_loop.py --> <!-- context: 验证 rework 次数限制、状态正确流转、超限时正确中断 --> <!-- order: 依赖循环实现完成 -->

### 测试文件关联修复

- [x] 修复测试文件关联的 import 匹配 <!-- files: src/opc/knowledge/test_association.py:68 --> <!-- context: f"from" in content 误报率高；改用正则匹配 import 语句 --> <!-- auto -->
- [x] 添加测试关��准确性验证 <!-- files: tests/test_test_association.py --> <!-- context: 用真实项目数据验证无误报、无漏报 --> <!-- order: 依赖 import 匹配修复 -->

---

## P2 - 代码质量与可维护性（影响长期维护）

### Agent 类拆分

- [x] 拆分 Agent 类为多个模块 <!-- files: src/opc/agent.py, src/opc/tools/, src/opc/security/ --> <!-- context: 当前 772 行违反单一职责；拆分为 agent.py（API 调用）、tools/（工具实现）、security/（安全检查） --> <!-- review: 需确认拆分边界和模块接口 -->
- [x] 更新 Agent 相关测试 <!-- files: tests/test_agent.py --> <!-- context: 拆分后更新 import 路径和测试用例 --> <!-- order: 依赖 Agent 拆分完成 -->

### RunStore 写入优化

- [x] RunStore 改为追加写入 <!-- files: src/opc/run_store.py:37-45 --> <!-- context: 当前每次追加都重写 trace，O(n²) 复杂度；改为追加到 JSONL，finalize 时写最终 trace --> <!-- auto -->
- [x] 添加 RunStore 性能测试 <!-- files: tests/test_run_store_append.py --> <!-- context: 验证追加写入性能，1000 次事件 <1s --> <!-- order: 依赖追加写入实现 -->

### Schema 跨字段校验

- [x] QAOutput 添加跨字段校验 <!-- files: src/opc/schema.py --> <!-- context: status="pass" + next_action="rework" 语义矛盾但能通过校验；添加 @model_validator 检查一致性 --> <!-- auto -->
- [x] 添加 Schema 校验测试 <!-- files: tests/test_qa_output_validator.py --> <!-- context: 验证矛盾组合被拒绝、合法组合通过 --> <!-- order: 依赖校验器实现 -->

### 测试导入路径统一

- [x] 统一测试文件导入路径 <!-- files: tests/*.py --> <!-- context: from src.opc.* 在 pip 安装后失败；全局替换为 from opc.* --> <!-- auto -->

### BM25 索引去 Pickle

- [x] BM25 索引改用 JSON 持久化 <!-- files: src/opc/knowledge/bm25_index.py:60-73 --> <!-- context: pickle 有安全风险且不可读；改用 JSON 持久化原始数据，加载时重建索引 --> <!-- auto -->
- [x] 添加 BM25 JSON 持久化测试 <!-- files: tests/test_bm25_json.py --> <!-- context: 验证 save/load 正确、跨版本兼容 --> <!-- order: 依赖 JSON 持久化实现 -->

---

## P3 - Harness Engineering 补强（系统可靠性）

- [x] 补齐 OPC Harness Engineering 生产化闭环 <!-- files: src/opc/agent.py, src/opc/roles.py, src/opc/workflow.py, src/opc/workflow_spec.py, src/opc/schema.py, src/opc/tools/, src/opc/store.py, src/opc/run_store.py, tests/ --> <!-- context: 责任角色: Architect（主责）/ 输入: README.md 产品定位、docs/什么是Harness.md 六层 Harness 参考、现有 Agent/Workflow/Schema/Tools/RunStore 实现、IMPROVEMENT_ROADMAP.md 与当前 Beta 任务清单 / 输出: 角色级工具白名单、按角色裁剪的 ContextPack、工具结果提炼机制、自动化验证与观测指标、QA 诊断式回退字段、产物版本管理、长期记忆与自修复试点、对应测试与验收记录 / 依赖关系: 依赖 P0 安全基线、P1 WorkflowSpec/异步/rework 修复、P2 Agent 拆分与 RunStore 优化完成后推进 / 完成标准: PM/Engineer/QA/Ops 等角色只获得必要工具；QA 阶段能运行确定性验证并记录证据；QAOutput 能区分 failure root cause 与建议回退阶段；rework 产物可按版本回溯；ContextPack 不再无差别携带所有阶段摘要；高噪声工具输出有摘要/裁剪；run_metrics/run_trace 能体现自动验证、工具调用、回退原因与自修复结果；新增定向测试通过 --> <!-- review -->

---

## P5 - Harness 资产完整性（文档与规则一致性）

### 结构性去重与索引修复

- [x] 去重 CLAUDE.md 与 discipline.md 的"默认策略" <!-- files: CLAUDE.md, docs/claude/discipline.md --> <!-- context: CLAUDE.md:29-35 与 discipline.md:56-64 逐条重复；CLAUDE.md 改为只保留索引指向 --> <!-- auto -->
- [x] 修复 plan.md 索引失效 <!-- files: docs/claude/discipline.md --> <!-- context: discipline.md:70 引用 plan.md 但仓库根不存在；改指现有 IMPROVEMENT_ROADMAP.md 或 tasks-p*.md --> <!-- review: 需决定指向哪个文件 -->
- [x] 在 CLAUDE.md 增补 .claude/ 资产索引 <!-- files: CLAUDE.md --> <!-- context: 当前文档结构表只列 docs/claude/*，未提 .claude/；新增一行说明 hooks/skills/permissions --> <!-- order: 依赖去重完成 -->

### 规则可执行性

- [x] 将关键纪律落到 settings.json 的 hooks <!-- files: .claude/settings.json --> <!-- context: discipline 全是 SHOULD 无强制；新增 PreToolUse hook：写入 CLAUDE.md/docs/claude/** 前强制确认；git push --force/reset --hard 显式 deny --> <!-- review: 需确认 hook 命令在 Windows bash 下可用 -->
- [x] roles.md 增加产出 → 模板交叉引用 <!-- files: docs/claude/roles.md --> <!-- context: 每个角色"必须产出"项后追加 standards.md 锚点链接，形成角色→产出→模板闭环 --> <!-- auto -->
- [x] standards.md 模板补充真实示例 <!-- files: docs/claude/standards.md --> <!-- context: 当前只有字段名；每节末尾追加 1 个仓库内真实文件链接作为参考样例 --> <!-- auto -->

### settings 权限治理

- [x] 清理 settings.json 中失效的 Bash 放行 <!-- files: .claude/settings.json --> <!-- context: 仍放行 pre_upload_check.sh 但该脚本已不存在；删除失效项 --> <!-- auto -->

### Skills 扩充

- [x] 新增 role-switch skill <!-- files: .claude/skills/role-switch/SKILL.md --> <!-- context: 支持 /role-switch PM 等调用，强制按 roles.md 对应角色"必须产出/禁止事项"结构输出 --> <!-- order: 依赖 roles.md 交叉引用补齐 -->
- [ ] 新增 task-spec skill <!-- files: .claude/skills/task-spec/SKILL.md --> <!-- context: 按 standards.md 的"任务清单"字段生成/追加 tasks-pX.md 条目 --> <!-- order: 依赖 standards 示例补齐 -->
- [ ] 新增 acceptance-check skill <!-- files: .claude/skills/acceptance-check/SKILL.md --> <!-- context: 按 standards.md 的"验收文档"模板输出 QA 结论 --> <!-- order: 依赖 standards 示例补齐 -->

### 一致��自动校验

- [ ] 增加术语漂移检测 hook <!-- files: .claude/settings.json --> <!-- context: discipline.md:30-40 列了 7 个统一术语，但无机制防止文档混入同义词；新增 PostToolUse hook 在写入 docs/**.md 后 grep 同义词命中则告警 --> <!-- order: 依赖 hook 基础设施 -->

---

## 生产就绪性检查

### Docker 镜像发布

- [ ] 验证 Docker 镜像构建流程 <!-- files: Dockerfile, .github/workflows/ --> <!-- context: Docker 镜像发布 workflow 已添加但未验证；本地构建并测试镜像可用性 --> <!-- auto -->
- [ ] 添加 Docker 镜像 smoke test <!-- files: tests/test_docker_smoke.py --> <!-- context: 验证镜像启动、opc --version、opc run 基础功能 --> <!-- order: 依赖镜像构建验证 -->

### CI/CD 自动化

- [ ] 添加 GitHub Actions CI 流水线 <!-- files: .github/workflows/ci.yml --> <!-- context: 当前无 CI 自动化；添加 pytest、lint、type check 自动执行 --> <!-- review: 需确认 CI 环境配置 -->
- [ ] 添加测试覆盖率报告 <!-- files: .github/workflows/ci.yml --> <!-- context: 在 CI 中生成覆盖率报告，要求 >80% --> <!-- order: 依赖 CI 流水线 -->

### 文档完整性

- [ ] 更新 README.md Beta 状态 <!-- files: README.md --> <!-- context: 当前标注"进行中"；完成所有任务后改为"已完成"，列出 Beta 核心能力 --> <!-- order: 依赖所有 Beta 任务完成 -->
- [ ] 编写 Beta 发布说明 <!-- files: docs/releases/beta-release-notes.md --> <!-- context: 总结 Beta 阶段新增能力、破坏性变更、升级指南 --> <!-- order: 依赖所有 Beta 任务完成 -->

---

## Beta 验收清单

完成以下验收项后，Beta 阶段可标记为完成：

### 安全性验收

- [ ] 无已知的路径遍历漏洞 <!-- context: P0.2 修复并有测试覆盖 -->
- [ ] 无已知的代码注入漏洞 <!-- context: 命令白名单生效 -->
- [ ] 成本控制 100% 生效 <!-- context: P0.3 硬限制生效并有测试 -->
- [ ] 工具调用可完整审计 <!-- context: run_trace.json 包含所有工具调用的输入/输出/耗时 -->

### 可用性验收

- [ ] 交互模式下 API 重试延迟 <30s <!-- context: P0.4 修复并有测试 -->
- [ ] 工作流失控率 <1% <!-- context: P0.1 循环终止保护生效 -->
- [ ] WorkflowSpec 完全驱动工作流 <!-- context: P1.2 修复并有集成测试 -->
- [ ] 异步上下文可正常调用 <!-- context: P1.1 修���并有测试 -->

### 可维护性验收

- [ ] 单个文件 <500 行 <!-- context: P2.1 Agent 拆分完成 -->
- [ ] 测试覆盖率 >80% <!-- context: 所有新增功能有测试 -->
- [ ] 所有测试在 pip install -e . 后可运行 <!-- context: P2.5 导入路径统一 -->
- [ ] 核心模块有文档字符串 <!-- context: Agent、Workflow、Schema 等核心类有完整 docstring -->

### 文档一致性验收

- [ ] CLAUDE.md 与 discipline.md 无重复段 <!-- context: P5 去重完成 -->
- [ ] discipline.md 中所有文档路径在仓库可解析 <!-- context: P5 索引修复完成 -->
- [ ] settings.json 中 Bash allow 项指向真实存在脚本 <!-- context: P5 权限治理完成 -->
- [ ] 新增 3 个 skill 可被 harness 识别 <!-- context: P5 skills 扩充完成 -->
- [ ] 触发高危命令时 hook 实际拦截 <!-- context: P5 规则可执行性完成 -->

---

## 工作量估算

按 IMPROVEMENT_ROADMAP.md 的时间线：

| 阶段 | 任务范围 | 预计工作量 | 可并行 |
|------|---------|-----------|--------|
| P0 修复 | 4 个安全/可用性红线 + 测试 | 1-2 周 | 否 |
| P1 核心功能 | 4 个功能缺陷 + 测试 | 2-3 周 | 部分可并行 |
| P2 代码质量 | 6 个重构项 + 测试 | 3-4 周 | 可与 P5 并行 |
| P5 Harness 资产 | 11 个文档/规则项 | 1-2 周 | 可与 P2 并行 |
| 生产就绪 | Docker + CI/CD + 文档 | 1 周 | 可与 P2/P5 并行 |

**总计约 6-8 周可达到 Beta 验收标准**。

---

## 优先级建议

### 第一周（阻塞性问题）
1. P0.4 - 交互模式重试延迟（影响 opc run 基本可用性）
2. P0.1 - 工具循环终止保护（防止失控）
3. P0.3 - 成本硬限制（防止超支）

### 第二周（安全基线）
4. P0.2 - 路径遍历修复
5. P0 测试覆盖
6. P1.2 - WorkflowSpec 驱动（核心架构）

### 第三-四周（功能完整性）
7. P1.1 - 异步上下文兼容（为 Web UI 铺路）
8. P1.3 - QA rework 循环
9. P1.4 - 测试关联修复

### 第五-六周（代码质量，可并行）
10. P2.1 - Agent 拆分
11. P2.3 - RunStore 优化
12. P2.4/2.5/2.6 - Schema/导入/BM25 修复
13. P5 全部（文档与规则）

### 第七周（生产就绪）
14. Docker 验证
15. CI/CD 流水线
16. 文档更新与发布说明

---

## 注意事项

1. **P0 必须优先**：安全和可用性问题会影响所有用户，必须立即修复
2. **测试先行**：所有修复必须有对应测试，避免回归
3. **文档同步**：代码变更后立即更新相关文档
4. **小步提交**：每个任务完成后立即提交，避免大批量合并冲突
5. **验收驱动**：以验收清单为目标，避免过度优化

---

## 参考文档

- [IMPROVEMENT_ROADMAP.md](IMPROVEMENT_ROADMAP.md) - 详细的技术改进清单
- [tasks-p5.md](tasks-p5.md) - Harness 资产优化任务
- [README.md](README.md) - 产品化路线图
- [docs/claude/discipline.md](docs/claude/discipline.md) - 执行纪律与默认策略
