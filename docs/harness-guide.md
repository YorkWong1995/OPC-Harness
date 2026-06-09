# OPC Harness Guide

> OPC 的完整项目手册：把 workflow、skills、agent、memory、RAG、tool use、trace 和使用流程放在同一张图里。

## 1. 文档定位

### 1.1 读者对象

这份文档面向三类读者：

- 想快速理解 OPC 整体结构的人。
- 准备在项目里使用 `opc run`、`opc index`、`opc query`、skills 或 agent 资产的人。
- 需要知道哪些能力已经实现、哪些只是设计中或路线图的人。

### 1.2 本文覆盖范围

本文覆盖 OPC 的完整 harness：

- 项目定位与能力边界
- workflow 与角色协作
- Claude Code skills
- `.claude/agents/` 里的 agent asset
- runtime agent 与 role factory
- memory 与长期上下文
- RAG / knowledge retrieval
- tool use、权限与 guardrail
- run、trace、artifact、checkpoint
- 常见使用流程

### 1.3 本文不覆盖范围

本文不替代以下文档：

- [README.md](../README.md) 的安装与快速开始。
- [docs/plan/](plan/) 下的长期规划文档。
- [docs/share/internal_technical_share.md](share/internal_technical_share.md) 的内部分享稿。
- [docs/什么是Harness.md](什么是Harness.md) 的概念科普。

如果你只想先跑起来，请先读 [README.md](../README.md)。如果你想理解“为什么这样设计”，继续读本文。

---

## 2. OPC 是什么

OPC 是一个面向“单人软件公司”的软件交付编排层。它不追求把模型变成万能员工，而是把模型、工具、角色、状态、记忆、检索、验证和人工介入组合成一个可执行的 harness。

对应的项目定位、愿景与路线图可以先看：

- [README.md](../README.md)
- [plan.md](../plan.md)
- [docs/plan/vision.md](plan/vision.md)
- [docs/plan/roadmap.md](plan/roadmap.md)

### 2.1 当前能力状态

OPC 在仓库中会按能力成熟度分成三类：

| 状态 | 含义 | 典型内容 |
| --- | --- | --- |
| Available | 已实现、可本地复现 | PM → Engineer → QA 最小工作流、结构化角色输出、run trace、知识索引与检索、本地 diagnostics、release report、workflow pack 发现 |
| Experimental | 部分实现或仍在收敛 | 动态多角色入口、工具链集成、低风险 workflow pack runtime smoke |
| Planned / Roadmap | 设计中或路线图 | OS 级运行时能力、自定义 workflow、完整恢复入口等 |

这份手册会在每一节尽量标注状态，避免把设计、规划和已实现能力混在一起。

### 2.1.1 P10 本地工业化入口

| 目标 | 命令 / 文档 |
| --- | --- |
| artifacts 只读体检 | `opc artifacts doctor --artifacts-dir <dir>` |
| index 只读体检 | `opc index-doctor --name <name>` |
| 清理候选 dry-run | `opc cleanup --root . --include all` 或 `python scripts/cleanup-dry-run.py` |
| workflow pack 发现 | `opc workflow-packs list` |
| 低风险 runtime smoke | `opc workflow-packs smoke --id docs-update` |
| 本地 release report | `python scripts/check-release.py --version local` |
| 轻量 RAG eval | `python scripts/run-rag-eval.py --top-k 3` |

这些入口默认不发布、不上传、不 push、不删除文件；会写入本地 report/artifact 的命令应在输出中明确报告路径。

### 2.2 OPC 现在最重要的目标

OPC 当前最重要的目标不是“更聪明”，而是“更可靠”：

- 需求可以被结构化。
- 任务可以被拆解和交接。
- 代码可以被修改和验证。
- 失败可以被定位和回退。
- 经验可以被记录、检索和复用。

---

## 3. 完整 Harness 地图

从系统视角看，OPC 的 harness 可以分成三层：

1. **组织层**：谁负责什么，任务怎么传递。
2. **执行基础设施层**：Agent 怎么调用工具、怎么管理上下文、怎么读写 memory、怎么接入知识库。
3. **评估与运维闭环层**：如何验证、记录、回退、恢复和复盘。

这个三层划分和架构说明一致，见 [docs/plan/architecture.md](plan/architecture.md)。

### 3.1 一次任务的基本路径

```text
用户输入
  → PM 结构化需求
  → 可选 Architect 判断方案
  → Engineer 实现
  → QA 验收
  → run/trace/artifact 留痕
  → memory / knowledge / docs 沉淀
```

### 3.2 Harness 里到底有什么

Harness 不是单个模型，也不是单个 workflow，而是一整套执行系统：

- 系统提示词
- 工具调用
- 文件系统
- 代码执行环境
- 工作流编排
- 角色分工
- 记忆系统
- 知识检索
- 评估与回退
- 审计与 trace

更多概念解释可参考 [docs/什么是Harness.md](什么是Harness.md)。

---

## 4. 核心概念边界

这一节是整份手册最重要的部分之一。很多概念名字相近，但职责完全不同。

| 概念 | 所在位置 | 作用 | 是否直接执行 |
| --- | --- | --- | --- |
| Claude Code skill | `.claude/skills/*/SKILL.md` | 面向 Claude 协作的可调用能力，如任务生成、验收、评审、发布检查 | 是，由 Claude Code 调用 |
| Agent asset | `.claude/agents/*` | 角色/任务配置说明，沉淀职责、输入输出、工具边界和禁止事项 | 否 |
| Runtime agent | `src/opc/agent.py` | 真实执行的 Agent 封装，负责模型调用、tool use、RAG、guardrail | 是，由 OPC workflow 执行 |
| Role factory | `src/opc/roles.py` | 根据角色创建 runtime agent，并绑定 prompt 与工具边界 | 间接执行 |
| Workflow pack | `docs/workflow-packs/*` | 一类任务的流程模板，定义输入、权限、产物、验收和 trace 边界 | 视 pack 类型而定 |
| Runtime workflow | `src/opc/workflow.py` | 真正的执行链路，负责阶段状态流转和角色调度 | 是 |
| Run | `artifacts/` 中的一次执行实例 | 一次 `opc run` 或 `opc resume` 的执行结果 | 否 |
| Artifact | run 的产物 | 报告、状态、metrics、trace、角色输出等 | 否 |
| Checkpoint | 恢复快照 | 只服务恢复，不等于长期 memory | 否 |
| Memory | `src/opc/memory.py` | 保存经过确认、可复用的长期事实或偏好 | 否 |
| RAG / knowledge retrieval | `src/opc/knowledge/*` + `opc index/query` | 让项目知识可检索、可引用、可注入上下文 | 否 |

### 4.1 你最容易混淆的三件事

#### 4.1.1 `skill` 不是 runtime agent

Skill 是 Claude Code 的协作能力包，通常通过 `/skill-name` 使用。它适合做：

- 任务拆解
- 验收检查
- 评审
- 发布检查
- 文档更新
- 代办规范化

它不是 OPC runtime workflow 的执行引擎。

#### 4.1.2 `agent asset` 不是可执行程序

`.claude/agents/` 里保存的是角色资产说明。它描述：

- 这个角色做什么
- 输入是什么
- 输出是什么
- 工具边界是什么
- 禁止做什么

它是稳定的说明文件，不是命令，不负责实际执行。

#### 4.1.3 `runtime agent` 才是真正干活的 Agent

`src/opc/agent.py` 里的 `Agent` 才是实际执行体。它会：

- 调 Claude API
- 按角色提示执行
- 调用工具
- 记录 token / API call / tool call
- 受 permission profile 和 guardrail 约束
- 在需要时接入 RAG

---

## 5. Workflow 体系

最小可验证闭环是 **PM → Engineer → QA**。这是 OPC 的默认主链路。

对应设计见：

- [docs/plan/workflow.md](plan/workflow.md)
- [docs/workflow-packs/README.md](workflow-packs/README.md)
- [src/opc/workflow.py](../src/opc/workflow.py)
- [src/opc/workflow_spec.py](../src/opc/workflow_spec.py)

### 5.1 最小闭环

| 角色 | 标准输入 | 标准输出 | 通过条件 |
| --- | --- | --- | --- |
| PM | 用户目标、业务问题、约束条件 | PRD、范围说明、验收标准 | 目标明确、范围可控、验收标准可检查 |
| Engineer | PM 输出、代码上下文、QA defects | 代码变更、实现摘要、测试或验证结果 | 实现完成且验证证据可复现 |
| QA | PM 验收标准、Engineer 输出、验证结果 | pass/fail、checked_items、evidence、defects、next_action | 结论明确且证据覆盖关键验收标准 |

### 5.2 可选角色

可选角色按任务启用，不是每次都默认参与。

| 角色 | 典型触发 | 作用 |
| --- | --- | --- |
| Architect | 架构、模块边界、接口、数据结构、技术取舍 | 提供方案判断 |
| Ops | 部署、发布、上线、环境、监控、回滚 | 提供运行与发布审查 |
| Growth | 用户研究、反馈、增长、竞品、实验 | 提供研究或增长判断 |
| CEO / 用户 | 范围确认、优先级、关键决策 | 做最终确认 |

手动覆盖通常通过 `opc run` 参数完成，例如 `--with-architect`、`--with-ops`、`--with-growth`、`--skip-architect`、`--ceo-review`。

### 5.3 工作流的标准状态

推荐状态流转如下：

`待澄清 → 已定义 → 已设计 → 已拆解 → 实现中 → 待验收 → 已通过 / 已退回 → 已复盘`

这条状态链很重要，因为它把“描述任务”变成了“可执行任务”。

### 5.4 人工介入节点

以下节点默认可以人工确认：

- PRD 完成后，确认目标与范围。
- 高影响技术方案出现时，确认取舍。
- 实现阶段需要高风险操作时，确认是否执行。
- 验收结论存在争议时，确认是否通过或调整标准。
- 复盘时，确认哪些经验要上升为项目规范。

### 5.5 Workflow Pack

Workflow pack 是一类任务的模板化流程。当前文档中常见的 pack 有：

- `bugfix`
- `review`
- `docs-update`
- `release-check`

它们把输入、输出、权限、验收标准和 trace 边界固定下来。第一版重点是“文档与约束模板”，不是全自动编排系统。

### 5.6 WorkflowSpec 与 StageContract

`src/opc/workflow_spec.py` 定义了更结构化的 workflow 契约，例如：

- `WorkflowSpec`
- `StageContract`
- `StageResult`
- `TransitionPolicy`

它们的意义是把 workflow 从“写死的状态机”逐步推进到“可声明、可验证的阶段契约”。

当前应把它理解为：**已存在的声明式基础 + 仍在演进的 workflow 引擎**。

---

## 6. Agent 体系

### 6.1 Runtime Agent

`src/opc/agent.py` 中的 `Agent` 是 runtime 层的核心。它封装了：

- Claude API 调用
- tool use 循环
- 最大工具轮次限制
- 角色提示词
- 权限配置
- guardrail 策略
- RAG 接入
- token / API call / tool call 统计

关键实现位置：

- [src/opc/agent.py](../src/opc/agent.py)
- [src/opc/tools/tool_registry.py](../src/opc/tools/tool_registry.py)
- [src/opc/tools/knowledge_tools.py](../src/opc/tools/knowledge_tools.py)

### 6.2 Role factory

`src/opc/roles.py` 负责把角色变成可执行 Agent：

- `create_pm_agent`
- `create_engineer_agent`
- `create_qa_agent`
- `create_architect_agent`
- `create_ceo_agent`
- `create_ops_agent`
- `create_growth_agent`
- `create_embedded_engineer_agent`

### 6.3 角色工具边界

不同角色的工具边界不同，这是 harness 控制力的关键。

| 角色 | 工具边界 |
| --- | --- |
| PM | 纯文本输出，不直接操作文件 |
| CEO | 纯文本输出，不直接操作文件 |
| Growth | 纯文本输出，不直接操作文件 |
| Architect | 只读工具为主：`read_file`、`list_files`、`grep`、`search_knowledge`、`git_status` / `git_diff` / `git_log` |
| QA | 只读工具和验证工具：`read_file`、`list_files`、`grep`、`search_knowledge`、`git_*`、`run_lint` / `run_typecheck` / `run_tests` |
| Ops | 在 QA 工具基础上增加 `run_build` |
| Engineer | 读写文件、执行命令、Git、检索等全套：含 `read_file`、`grep`、`search_knowledge`、`write_file`、`edit_file`、`run_*` |
| Embedded Engineer | 与 Engineer 类似，但可启用 RAG |

检索类工具（`grep` 与 `search_knowledge`）对 Architect、QA、Ops、Engineer 均开放，所以**编码阶段同样可以查询代码与知识**，不是只读角色专属。两者的区别见第 9.6 节的选择规则。

这些边界来自 [src/opc/roles.py](../src/opc/roles.py) 与 [docs/claude/roles.md](claude/roles.md)。

### 6.4 Agent 与 skill 的关系

- skill 是 Claude Code 层的协作能力。
- runtime agent 是 OPC 执行层的工作单元。
- skill 更像“怎么协作”，runtime agent 更像“怎么干活”。

### 6.5 Agent 运行时约束

`Agent` 不是无限制自治系统。它有明确约束：

- 最大 tool rounds，防止死循环。
- retry mode，控制上游波动重试节奏。
- permission profile，限制工具可见性。
- dangerous command policy，限制高风险操作。
- audit log，记录危险命令和工具调用。

---

## 7. Skills 体系

Skills 是 Claude Code 层面的可调用协作能力，通常通过 `/xxx` 方式使用。

### 7.1 本仓库常见 skills

当前仓库中常见的 skills 包括：

- `task-spec`
- `implementation-check`
- `acceptance-check`
- `bugfix`
- `review`
- `release-check`
- `test-spec`
- `token-report`
- `role-switch`
- `internal-share-doc`

它们的完整说明在 `.claude/skills/*/SKILL.md`。

### 7.2 skill 的使用方式

常见用途：

- 任务要先结构化：用 `task-spec`。
- 代码完成后自检：用 `implementation-check`。
- 做 QA 验收：用 `acceptance-check`。
- 做只读评审：用 `review`。
- 交付前看发布风险：用 `release-check`。
- 统计 run token / cost：用 `token-report`。
- 生成内部分享稿：用 `internal-share-doc`。

### 7.3 skill 与 workflow pack 的区别

- skill 是 Claude Code 的“协作动作”。
- workflow pack 是 OPC 任务类型的“流程定义”。
- 两者可以对应，但不是同一个概念。

例如：

- `review` skill 适合只读评审。
- `review` workflow pack 可以定义更完整的角色、产物、权限和 trace 规则。

---

## 8. Memory 体系

Memory 负责保存“已经确认、可复用、跨任务仍然有效”的内容。

### 8.1 Memory 的数据范围

`src/opc/memory.py` 定义了以下 scope：

- `user`
- `project`
- `workflow`
- `run`
- `artifact`

其中长期 memory 主要是：

- `user`
- `project`
- `workflow`

短期/临时内容是：

- `run`
- `artifact`

### 8.2 MemoryRecord 的核心字段

每条 memory 记录通常包含：

- `id`
- `scope`
- `content`
- `source`
- `confidence`
- `created_at`
- `updated_at`
- `expires_at`
- `superseded_by`

### 8.3 写入策略

memory 写入不是“想到什么就存什么”，而是有明确筛选：

- 敏感内容拒绝。
- 临时调试内容拒绝。
- 缺少 source 拒绝。
- `run` / `artifact` scope 不进入长期 memory。
- 长期 memory 默认需要确认。

### 8.4 Memory 与 artifact / trace 的区别

- **artifact**：保存一次 run 的证据、状态和输出。
- **trace**：保存一次 run 的事件轨迹和过程信息。
- **memory**：保存经过确认、可复用的长期事实。

它们不是同一层东西。

### 8.5 Memory 如何进入上下文

`select_memory_for_context` 会按角色、scope、过期状态和当前事实筛选 memory，再决定是否注入上下文。

原则是：

- 当前 workspace 文件事实优先。
- memory 只能作为候选上下文。
- 若和当前事实冲突，不能直接覆盖当前事实。

---

## 9. RAG 与 Knowledge Retrieval

OPC 的知识检索不是单一路径，而是一个组合系统。

设计文档见 [docs/knowledge-retrieval-design.md](knowledge-retrieval-design.md)。

### 9.1 当前目标

目标是让系统能：

- 输入多个目录或文件。
- 对模糊问题和精确问题都能定位。
- 返回文件路径、行号和相关上下文。
- 供 CLI、runtime agent 和人工用户复用。

### 9.2 索引链路

知识索引由这些组件组成：

- `chunker.py`：分块。
- `indexer.py`：索引编排。
- `bm25_index.py`：关键词检索。
- `vector_store.py`：向量检索。
- `embedder.py`：embedding 生成。
- `models.py`：chunk / retrieval 数据模型。
- `import_graph.py`：依赖图。
- `symbol_search.py` / `cpp_symbol_search.py`：符号级定位。
- `impact_analyzer.py`：影响分析。
- `test_association.py`：测试关联。

### 9.3 检索链路

`src/opc/knowledge/retriever.py` 负责：

1. query profile 构建。
2. query rewrite。
3. vector 检索。
4. BM25 检索。
5. RRF 融合。
6. query bias。
7. context expansion。

它的核心思想是：

- 向量检索负责语义召回。
- BM25 负责关键词精确命中。
- RRF 负责把两路结果融合。
- context expansion 负责补全上下文。

### 9.4 RAG 与 memory 的区别

- **RAG**：把项目事实找回来。
- **memory**：把已经确认过的经验记住。

RAG 面向“定位事实”，memory 面向“沉淀经验”。

### 9.5 Agent 如何调用知识检索

`src/opc/tools/knowledge_tools.py` 提供 `search_knowledge` 工具，runtime agent 可以通过它检索项目知识。

这意味着知识检索不是只有 CLI 用户能用，Agent 在执行时也能查项目知识。

### 9.6 grep 与 search_knowledge 的选择规则

OPC 的检索其实有两条并行路径，对应两类不同的查询需求：

| 工具 | 实现 | 适用场景 | 特点 |
| --- | --- | --- | --- |
| `grep` | ripgrep 优先，回退 Python re（`src/opc/tools/file_tools.py`） | 已知确切符号、字符串或正则，如某个异常类、函数名、配置项在哪 | 精确、实时、无需索引、省 token |
| `search_knowledge` | 向量 + BM25 + RRF 混合检索（`src/opc/knowledge/retriever.py`） | 只知道意图或概念，如“登录鉴权逻辑在哪”“项目怎么处理重试” | 语义召回、跨文件聚合、需预先建索引 |

推荐分流：

- **知道确切名字** → 用 `grep`，最快也最准。
- **只描述得出意图** → 用 `search_knowledge` 做语义召回。
- **grep 命中后想看上下文** → 用 `read_file` 读完整片段。

两条路径互补，不是二选一。`grep` 解决“精确定位”，`search_knowledge` 解决“模糊定位”，多数任务会交替使用。这与 Claude Code 的 grep/glob/read 思路一致，OPC 在此之上额外提供了语义检索能力。

### 9.7 当前实现边界

当前文档和代码已经支持：

- 混合检索。
- line-level 引用。
- 代码意图偏置。
- 上下文扩展。
- 工具级检索（`grep` 精确检索 + `search_knowledge` 语义检索）。

但下面这些仍应按“设计中”理解，不要写成已全面完成：

- 全量 rerank 流水线。
- 完整多层语义 chunk。
- 完整 Agentic RAG 的自主闭环。
- 服务化、跨项目共享知识控制面。

---

## 10. Tool Use、权限与 Guardrail

### 10.1 Tool use 在 OPC 中的位置

Tool use 是 runtime agent 能执行任务的核心接口。没有工具，Agent 只能说；有工具，Agent 才能做。

### 10.2 权限模型

`src/opc/agent.py` 支持不同 permission profile：

- `read-only`
- `write`
- `execute`
- `dangerous`

这不是“是否真的危险”的判断，而是“工具可见性和策略层级”的判断。

### 10.3 危险命令策略

危险命令策略包括：

- `allow`
- `deny`
- `approval`
- `audit`
- `stop`

它们控制高风险动作是直接阻断、要求人工确认、记录警告还是终止 workflow。

### 10.4 工具注册和审计

工具通过统一注册表管理，通常会记录：

- 工具名
- 输入 schema
- 输出 schema
- 权限
- side effect
- timeout

`Agent` 还会记录：

- token 用量
- API 调用次数
- tool call 次数
- 危险命令事件

### 10.5 guardrail 的正确理解

guardrail 不是“绝对安全保证”。它的作用是：

- 限制可见工具。
- 拦截高风险动作。
- 记录审计痕迹。
- 给人工介入留出口。

---

## 11. 日常使用流程

这一节回答“我平时怎么用 OPC”。

### 11.1 基础初始化

从 `README.md` 里的最小流程开始：

1. `opc init`
2. `opc doctor`
3. `opc config validate`

这一步是为了确认当前环境、配置和 workspace 可用。

### 11.2 运行一个最小 harness 任务

典型命令是：

- `opc run "帮我设计一个用户登录功能"`
- `opc run "帮我设计一个用户登录功能" --project demo-login`
- `opc run "补充登录功能验收标准" --project-dir . --skip-architect`

适合：

- 需求结构化
- 实现任务
- 验收任务
- 文档到实现的小闭环

### 11.3 查看 run 和 trace

常用命令：

- `opc runs list`
- `opc trace summary --artifacts-dir ...`
- `opc trace show --artifacts-dir ... --limit 20`
- `opc runs cost --limit 10`

用来做：

- 复盘
- 验收
- 成本观察
- 失败定位

### 11.4 构建和查询知识索引

常用命令：

- `opc index --name myproject --dirs src/opc`
- `opc index --name docs --dirs docs/ README.md --extensions .py .md`
- `opc query "如何构建知识索引" --name myproject`
- `opc query "RAG 检索流程" --name myproject --no-llm`

适合：

- 文档问答
- 代码定位
- 项目知识回查
- 交给 Agent 查询上下文

### 11.5 使用 skills

当你在 Claude Code 里工作时，可以用 skill 完成特定动作：

- 任务规格化：`/task-spec`
- 代码实现自检：`/implementation-check`
- 验收：`/acceptance-check`
- 评审：`/review`
- 发布前检查：`/release-check`
- 成本报告：`/token-report`
- 内部分享：`/internal-share-doc`

### 11.6 选择哪条流程

#### 场景 A：我要改功能

推荐：

1. `task-spec`
2. `opc run` 或对应 runtime workflow
3. `implementation-check`
4. `acceptance-check`

#### 场景 B：我要只读评审

推荐：

- `review` skill
- 或 `opc trace summary` / `opc trace show` 查看证据

#### 场景 C：我要查项目知识

推荐：

- 已知确切符号 / 字符串：runtime agent 的 `grep` 工具（精确、快）
- 只知道意图 / 概念：`opc index` 建索引后用 `opc query` 或 runtime agent 的 `search_knowledge`（语义召回）
- 命中后看上下文：`read_file`

选择规则详见第 9.6 节。

#### 场景 D：我要写内部分享稿

推荐：

- `internal-share-doc` skill
- 参考本手册和 `docs/share/internal_technical_share.md`

---

## 12. 项目结构导览

### 12.1 顶层入口

- [README.md](../README.md)：项目入口、安装、CLI 使用。
- [CLAUDE.md](../CLAUDE.md)：Claude 协作规范入口。
- [plan.md](../plan.md)：项目总纲索引。

### 12.2 docs 目录

- `docs/plan/`：愿景、架构、组织、workflow、roadmap。
- `docs/claude/`：角色、标准、纪律。
- `docs/workflow-packs/`：workflow pack 说明。
- `docs/share/`：内部分享文档。
- `docs/knowledge-retrieval-design.md`：知识检索设计。
- `docs/什么是Harness.md`：Harness 概念说明。
- `docs/harness-guide.md`：本文。

### 12.3 .claude 目录

- `.claude/skills/`：Claude Code skills。
- `.claude/agents/`：agent asset。

### 12.4 src/opc 目录

关键模块包括：

- `agent.py`
- `roles.py`
- `workflow.py`
- `workflow_spec.py`
- `memory.py`
- `rag.py` / `rag_bm25.py`
- `knowledge/`
- `tools/`

### 12.5 knowledge 子系统

`src/opc/knowledge/` 是 OPC 的知识检索子系统，负责：

- 切块
- 建索引
- 向量存储
- BM25
- 检索融合
- 符号搜索
- 影响分析
- 测试关联

---

## 13. 维护规范与边界

### 13.1 文档维护原则

如果下面这些东西变了，这份手册也应该跟着更新：

- 角色职责
- 工具边界
- workflow 流程
- skills 清单
- memory 策略
- RAG 检索链路
- run / trace / artifact 语义
- CLI 命令入口

### 13.2 能力状态标注原则

写本文档时，优先使用下面四类描述：

- 已实现
- 部分实现
- 设计中
- 文档约定

不要把“设计中”写成“已经完成”，也不要把“规划”写成“当前默认能力”。

### 13.3 当前项目边界

OPC 目前应按 **本地单人 CLI harness** 理解，而不是：

- 团队级共享控制面
- 多租户服务平台
- 完整 OS 级运行时
- 默认自治的后台代理系统

### 13.4 与其他文档的关系

- README 负责“怎么开始”。
- 本文负责“完整怎么看懂”。
- 内部分享稿负责“怎么讲给别人听”。
- Harness 概念文档负责“什么是 harness”。
- 规划文档负责“未来要往哪里走”。

---

## 14. 参考文件索引

优先阅读顺序建议：

1. [README.md](../README.md)
2. [docs/plan/vision.md](plan/vision.md)
3. [docs/plan/architecture.md](plan/architecture.md)
4. [docs/plan/workflow.md](plan/workflow.md)
5. [docs/claude/roles.md](claude/roles.md)
6. [docs/claude/standards.md](claude/standards.md)
7. [docs/claude/discipline.md](claude/discipline.md)
8. [docs/knowledge-retrieval-design.md](knowledge-retrieval-design.md)
9. [docs/share/internal_technical_share.md](share/internal_technical_share.md)
10. [docs/什么是Harness.md](什么是Harness.md)
11. [src/opc/agent.py](../src/opc/agent.py)
12. [src/opc/roles.py](../src/opc/roles.py)
13. [src/opc/workflow.py](../src/opc/workflow.py)
14. [src/opc/workflow_spec.py](../src/opc/workflow_spec.py)
15. [src/opc/memory.py](../src/opc/memory.py)
16. [src/opc/knowledge/retriever.py](../src/opc/knowledge/retriever.py)
17. [src/opc/knowledge/indexer.py](../src/opc/knowledge/indexer.py)
18. [src/opc/tools/knowledge_tools.py](../src/opc/tools/knowledge_tools.py)

---

## 15. 一句话总结

OPC 的 harness 本质上是：把模型放进一个可执行、可验证、可恢复、可观测、可干预的软件交付系统里，让它不只是会回答问题，而是能稳定地完成任务。