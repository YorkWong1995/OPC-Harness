# P4: CTO 审查改进路线（基于 IMPROVEMENT_ROADMAP.md）

> 来源：CTO 级技术审查后对 OPC 项目的改进清单，覆盖安全/可用性红线、核心功能缺陷、代码质量、Roadmap 已知项与长期优化方向。详见 [IMPROVEMENT_ROADMAP.md](IMPROVEMENT_ROADMAP.md)。
> 格式遵循项目任务系统：`- [ ] 任务描述 <!-- files: ... --> <!-- context: ... -->`。
> 执行标注：`review`=需要人工取舍/评审后再做；`order`=必须在前置任务完成后顺序执行；`auto`=可由 Agent 小步直接执行；`decision`=已确认的决策。
> 测试策略：每个子任务优先跑定向测试，阶段性再扩大回归。

## 1. P0 - 安全与可用性红线（必须立即修复）

- [x] Agent 工具循环增加最大轮次保护 <!-- files: src/opc/agent.py, tests/test_tool_retry.py --> <!-- context: agent.py:153 当前 while True 无上限，失控会持续烧 token；新增 max_tool_rounds 默认 15，超限返回 [TRUNCATED] 文本并写 run_store 事件 --> <!-- auto: 改 Agent.__init__ + run() + 补一条单元测试 -->
- [x] 路径遍历检查改用 Path.is_relative_to <!-- files: src/opc/agent.py, tests/ --> <!-- context: agent.py:758-764 当前用 startswith，/home/user/proj 会匹配 /home/user/projectX；改用 Python 3.9+ 的 is_relative_to；同步检查 _check_command_allowed 中 agent.py:752 处的相同模式 --> <!-- auto: 单点替换 + 补穿越用例测试 -->
- [x] 成本控制增加硬限制 <!-- files: src/opc/config.py, src/opc/workflow.py, tests/ --> <!-- context: workflow.py:337-356 仅 print 警告；新增 workflow_token_hard_limit/role_token_hard_limit/enforce_hard_limit，超限抛 _StopWorkflow；保留原 soft_limit 警告行为 --> <!-- decision: soft + hard 双限 -->
- [x] API 重试间隔区分交互/批处理模式 <!-- files: src/opc/agent.py, src/opc/cli.py --> <!-- context: agent.py:22 默认 1800s 对 opc run 不可用；新增 mode 参数（interactive=10s, batch=1800s）或 OPC_RETRY_MODE 环境变量；CLI 默认 interactive --> <!-- decision: 默认交互模式 -->
- [x] P0 项验收：跑定向测试覆盖 4 项修复 <!-- files: tests/ --> <!-- context: 工具循环超限、路径穿越、token 硬限、重试间隔短延迟均需有用例；不跑全量回归 --> <!-- order: 依赖前 4 项 P0 完成 -->

## 2. P1 - 核心功能缺陷

- [x] 修复 asyncio.run 与同步代码混用 <!-- files: src/opc/workflow.py --> <!-- context: workflow.py:635 同步 run() 内嵌 asyncio.run，未来 Web UI/FastAPI 调用会抛 RuntimeError；推荐方案 A 全异步化（HarnessWorkflow.run → async），CLI 入口用 asyncio.run；备选方案 B 用 ThreadPoolExecutor --> <!-- review: 需确认走方案 A 还是 B；A 改动大但更彻底 -->
- [x] 让 WorkflowSpec 真正驱动状态流转 <!-- files: src/opc/workflow.py, src/opc/workflow_spec.py, tests/test_workflow_spec.py --> <!-- context: workflow.py:595-612 当前 if-elif 链，与 DEFAULT_WORKFLOW_SPEC 完全脱节；改为 handler_map 查表 + spec.next_state 决定流转；如果不打算用则删除 workflow_spec.py --> <!-- decision: 让 spec 生效，保留声明式优势 -->
- [x] QA rework 改为循环替代递归 <!-- files: src/opc/workflow.py, tests/ --> <!-- context: workflow.py:890 当前 return self._exec_qa(...) 递归依赖 completed_stages 隐式不变量；改为 while rework_attempts < max_rework_attempts 循环，状态变量显式化 --> <!-- auto: 单函数重构 + 跑现有 QA rework 测试 -->
- [x] 修复 _find_by_import 误报 <!-- files: src/opc/knowledge/test_association.py, tests/test_test_association.py --> <!-- context: test_association.py:68 当前 f"from" in content and module_name in content 会误匹配任何含 from 和模块名的文件；改用 regex 精准匹配 import/from import 语句；补真实项目数据用例 --> <!-- auto: 单函数修复 -->
- [ ] P1 项验收：Web UI 原型可在 async 上下文中跑 workflow <!-- files: tests/, examples/ --> <!-- context: 验证 P1.1 修复后能在 FastAPI 或 asyncio 协程中调用 HarnessWorkflow.run() 不报错 --> <!-- order: 依赖 P1.1 异步修复完成 -->

## 3. P2 - 代码质量与可维护性

- [x] 拆分 Agent 类（772 行 → 多模块） <!-- files: src/opc/agent.py, src/opc/tools/, src/opc/security/ --> <!-- context: agent.py 当前混合 API 调用、13 个工具实现、路径安全、命令白名单；建议拆为 tools/{file,search,git,build,command}_tools.py 与 security/{path_validator,command_whitelist,audit}.py；保留 agent.py 仅做 API 与 tool use 循环 --> <!-- order: 依赖 tool_registry 协议稳定；建议在 P0/P1 完成后做 -->
- [x] RunStore 写入优化 <!-- files: src/opc/run_store.py --> <!-- context: run_store.py:34 每次 append 都重写整个 trace 文件 → O(n²)；改为 append 只写 events.jsonl，结束时调用 finalize() 写 run_trace.json --> <!-- auto: 单文件改造 + 现有测试应能通过 -->
- [x] QAOutput 增加跨字段一致性校验 <!-- files: src/opc/schema.py, tests/ --> <!-- context: schema.py:111-116 当前 status=pass + next_action=rework 能通过校验；用 @model_validator(mode='after') 拒绝矛盾组合 --> <!-- auto: 加 validator + 补 negative test -->
- [x] 测试导入路径统一为 from opc. <!-- files: tests/ --> <!-- context: 12 个测试文件用 from src.opc. 在 pip install -e . 后会 ImportError；用 sed 全局替换；CI 加检查 grep -r "from src.opc" tests/ && exit 1 --> <!-- auto: sed 一次替换并跑测试 -->
- [x] BM25 索引去 Pickle <!-- files: src/opc/knowledge/bm25_index.py, tests/ --> <!-- context: bm25_index.py:60-73 当前 pickle.dump/load；改为 JSON 持久化原始 chunks，加载时调 self.build() 重建索引（成本低）；防御纵深 + 让索引可读可迁移 --> <!-- auto: 单文件改造 -->
- [ ] P2.2 异常用于流程控制（讨论项，暂不重构） <!-- files: src/opc/workflow.py --> <!-- context: _GoBack/_StopWorkflow 是私有异常用于状态机流转，类似 StopIteration 是可接受模式；仅在未来引入嵌套工作流时再改 StageResult 返回值 --> <!-- review: 不立即动手；仅保留为待观察项 -->
- [ ] P2 项验收：覆盖率 >80% 且 pip 安装后测试可跑 <!-- files: tests/ --> <!-- context: P2 完成后跑一次定向回归（不跑全量套件，避免冻 PC） --> <!-- order: 依赖 P2 上述项目完成 -->

## 4. P3 - Roadmap 已知项（非缺陷，按节奏推进）

- [ ] 支持 C/C++ 符号搜索（ctags 方案） <!-- files: src/opc/knowledge/cpp_symbol_search.py --> <!-- context: 当前只支持 Python AST；新增 CppSymbolSearch 调用 ctags 生成 .tags 并解析；让 OPC 在 C/C++ 项目可用到符号级定位 --> <!-- order: 依赖 ctags 命令在用户机器可用；评估 LSP 方案作为后续升级 -->
- [ ] 替换 ChromaDB 为 faiss-cpu <!-- files: src/opc/knowledge/vector_store.py --> <!-- context: 本地单用户场景下 faiss 更轻量；用 IndexFlatL2 + id_map JSON 持久化；保留 ChromaDB 适配作为可选 backend --> <!-- review: 需确认是否完全替换还是保留两套；评估迁移现有索引的成本 -->
- [ ] 默认使用中文 Embedding 模型 <!-- files: src/opc/knowledge/embedder.py, src/opc/config.py --> <!-- context: 当前 MiniLM 不支持中文，主要用户是中国独立开发者；默认改为 BAAI/bge-small-zh-v1.5 或 shibing624/text2vec-base-chinese；维度需对应调整 --> <!-- decision: 默认中文模型 -->
- [ ] 角色激活改用 LLM 分类 <!-- files: src/opc/roles.py --> <!-- context: roles.py:394-400 当前关键词匹配会误触；改为用 claude-haiku 做一次轻量分类；同时保留 CLI flag --with-architect/--with-ops 让用户显式选 --> <!-- review: 需评估每次启动都跑一次 LLM 分类的成本 vs CLI flag 的简洁性 -->
- [ ] P3 项验收：C/C++ 项目符号搜索可用，中文 RAG 准确率提升 >30% <!-- files: tests/, examples/ --> <!-- context: 准备一个 C/C++ sample 项目和一组中文查询基准做 A/B 验证 --> <!-- order: 依赖前面 P3 项完成 -->

## 5. 长期优化方向 - 架构层面

- [ ] 完整 LSP 集成统一多语言符号查询 <!-- files: src/opc/knowledge/ --> <!-- context: 用 LSP 协议统一 Python/C++/其他语言的 symbol/definition/references 查询；替代分语言的临时方案 --> <!-- review: 重大架构决定，需确认值得投入；可能晚于 v1 -->
- [ ] 工作流引擎完全由 WorkflowSpec 驱动 <!-- files: src/opc/workflow.py, src/opc/workflow_spec.py --> <!-- context: 在 P1.2 基础上扩展 spec：支持 retry/approval/parallel/sub-workflow 字段；目标是用户可通过修改 spec 改变工作流行为 --> <!-- order: 依赖 P1.2 spec 接入完成 -->
- [ ] 支持自定义工作流（YAML/TOML 定义流程） <!-- files: src/opc/workflow_spec.py, opc.toml --> <!-- context: 用户可在 opc.toml 或单独 YAML 文件中定义自己的角色顺序、状态流转规则；OPC 加载并执行 --> <!-- order: 依赖完整 WorkflowSpec 驱动；P1.2 → 完整 spec → 自定义 -->
- [ ] 子工作流支持 <!-- files: src/opc/workflow.py --> <!-- context: 例如 Engineer 内部的 code → test → lint 子链路；需要解决子工作流状态隔离与父子事件关联 --> <!-- review: 需先评估 Engineer 是否真的需要子工作流，还是用工具调用即可 -->

## 6. 长期优化方向 - 功能层面

- [ ] C/C++ #include 依赖分析 <!-- files: src/opc/knowledge/import_graph.py --> <!-- context: 用 compile_commands.json + 头文件扫描；处理头文件搜索路径、条件编译、宏展开等复杂度 --> <!-- order: 依赖 P3 C/C++ 符号搜索完成 -->
- [ ] 跨语言项目支持（Python + C++ 混合） <!-- files: src/opc/knowledge/ --> <!-- context: Python 调用 C++ 扩展（pybind11/cython）的项目；需要在符号搜索和依赖分析中跨越语言边界 --> <!-- order: 依赖 C/C++ 符号搜索 + import 图均到位 -->
- [ ] Rerank 模型精排（bge-reranker-v2-m3） <!-- files: src/opc/knowledge/ --> <!-- context: 在 hybrid retrieval（BM25 + 向量）后再用 reranker 精排 top-k；提升召回 → 排序的质量 --> <!-- review: 评估单机推理成本与延迟是否可接受；可能仅在批处理模式启用 -->
- [ ] Agentic RAG（多轮检索） <!-- files: src/opc/knowledge/, src/opc/agent.py --> <!-- context: 让 Agent 自主决定何时检索、检索什么、是否扩展查询；替代当前一次检索一次拼接的策略 --> <!-- review: 需评估对延迟和成本的影响；建议先在 PM/Architect 阶段试点 -->
- [ ] 上下文扩展（召回 chunk 后自动扩展相关内容） <!-- files: src/opc/knowledge/ --> <!-- context: 召回某 chunk 后自动加载其所在文件、相邻 chunk、相关测试文件等；让 Engineer 拿到的上下文更完整 --> <!-- order: 依赖测试文件关联和 import graph 已落地 -->

## 7. 长期优化方向 - 工程层面

- [ ] Web UI 完整实现 <!-- files: src/opc/ui/, src/opc/ --> <!-- context: 替代当前 CLI/简单 UI，提供工作流可视化、人工介入、历史回放；前端技术栈待定 --> <!-- order: 依赖 P1.1 异步化完成 + run trace 字段稳定；review: 需先确定目标用户使用场景 -->
- [ ] 多项目管理 <!-- files: src/opc/cli.py, src/opc/config.py --> <!-- context: 用户可同时管理多个项目的 OPC 配置/历史/索引；CLI 加 opc switch <project> 等命令 --> <!-- review: 需先评估单用户是否真有多项目并发需求 -->
- [ ] 工作流可视化（timeline、依赖图） <!-- files: src/opc/ui/ --> <!-- context: 在 Web UI 中展示 run trace 的时间轴、角色依赖、工具调用链；帮助用户复盘 --> <!-- order: 依赖 Web UI 完整实现 -->
- [ ] 插件市场（社区贡献工具和角色） <!-- files: src/opc/tools/, src/opc/roles.py --> <!-- context: 在 plugin tools 基础上扩展为可发布/安装的插件包；需要插件签名、版本管理、安全审查机制 --> <!-- review: 重大产品决定；需先评估社区规模 -->
- [ ] Docker 镜像发布 <!-- files: Dockerfile, .github/ --> <!-- context: 提供 opc:latest 镜像让用户一键试用；包含预置 embedding 模型、ctags 等依赖 --> <!-- auto: 可作为产品化前置工作 -->

## 8. 度量指标（验收时检查）

- [ ] 安全性指标：无路径遍历漏洞、无代码注入漏洞、成本控制 100% 生效 <!-- context: 对应 P0.1/P0.2/P0.3；需要至少一条针对每条的负向测试 -->
- [ ] 可用性指标：交互模式 API 重试 <30s、工作流失控率 <1%、中文 RAG 准确率 >70%（当前约 40-50%） <!-- context: 对应 P0.1/P0.4/P3.3；中文 RAG 需要基准查询集 -->
- [ ] 可维护性指标：单文件 <500 行、单函数 <100 行、测试覆盖率 >80% <!-- context: 对应 P2.1；agent.py（772 行）和 workflow.py（1077 行）是当前主要超标项 -->
- [ ] 性能指标：索引构建 >1000 文件/分钟、查询响应 <2s（不含 LLM）、状态保存 <100ms <!-- context: 对应 P2.3 和 P3.2；需建立性能基准测试 -->

## 备注

- **优先级原则**：P0 → P1 → P2.1-2.5 → P3 → 长期方向；P2.2 暂不动手。
- **测试纪律**：避免一次跑全量测试套件冻 PC；每条任务完成后只跑该范围的定向测试。
- **决策溯源**：所有 `decision` 标注的项已在 IMPROVEMENT_ROADMAP.md 修订说明中记录依据。
