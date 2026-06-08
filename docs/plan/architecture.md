# 三层系统架构与关键能力

## 1. 三层系统架构

本项目采用三层结构，把组织协作、执行基础设施和验证运维闭环分开设计。

### 1.1 组织层

组织层参考 MetaGPT 一类的多角色协同思想，核心关注点是：

- 谁负责什么
- 角色如何传递结果
- 不同角色的输入输出标准是什么
- 任务如何按职责链路向下分发

这一层负责建立"公司"本身的组织结构。

### 1.2 执行基础设施层

执行基础设施层参考 OpenHarness / OpenHands / OpenDevin 一类项目的能力抽象，核心关注点是：

- Agent 可以调用哪些工具
- 工具如何统一封装为 Skills / Actions
- 如何管理短期上下文、长期记忆与项目文档
- 如何限制高风险操作权限
- 如何支持代码、终端、API、数据库等执行环境

这一层负责建立"公司员工做事的工作台"。

### 1.3 评估与运维闭环层

评估与运维闭环层参考 Harness 与 Anthropic 在 agent workflow 上强调的运行机制，核心关注点是：

- 任务是否被拆解为可执行步骤
- 生成结果如何被校验
- 哪些节点必须有人类介入
- 如何记录运行轨迹、指标与失败案例
- 如何在失败后回退、修复和优化

这一层负责建立"公司如何保证质量与持续运行"。

## 2. Harness Engineering 方法论边界

Harness Engineering 在 OPC 中不是替代 SDLC、DevOps 或 Agile 的新流程名称，而是一组面向 AI Agent 工作流的工程约束。它关注的是：如何把不稳定的模型输出放进可执行、可验证、可恢复、可观测的交付轨道中。

| 对比对象 | 主要关注点 | Harness Engineering 的区别 |
| --- | --- | --- |
| SDLC | 软件从需求、设计、实现、测试到维护的生命周期 | 不重新定义生命周期阶段，而是把每个阶段转成 Agent 可接收的输入、输出和验收协议 |
| Agile | 迭代节奏、反馈循环、需求优先级和团队协作方式 | 不规定组织节奏，而是约束单次 Agent 任务如何小步交付、被检查、被退回 |
| DevOps | 构建、发布、运行、监控和反馈链路 | 不替代部署运维体系，而是把工具调用、权限、trace、失败记录纳入可审计工作流 |

因此，OPC 的架构重点不是“更多角色”或“更自治”，而是让每一次 AI 参与的软件交付都具备以下性质：

- **可执行**：输入足够明确，角色知道下一步做什么。
- **可验证**：输出有验收标准、测试或证据。
- **可恢复**：状态、消息、产物和失败原因可被追踪，后续可以接续处理。
- **可观测**：运行过程、工具调用、token、错误和最终状态可复盘。
- **可干预**：高风险决策或不确定结果能升级给人类。

## 3. 系统关键能力

为了支撑以上三层结构，系统至少需要具备以下能力：

1. **任务规划能力**：能把高层需求拆解为角色可执行任务。
2. **角色路由能力**：能把任务正确分配给合适角色。
3. **工具调用能力**：能通过统一接口访问代码、终端、Git、API、数据库等工具。
4. **记忆与上下文能力**：能管理当前任务上下文、项目规范、历史经验。
5. **权限与安全能力**：高风险操作默认受限，关键动作可审批。
6. **验证与评估能力**：结果必须经过测试、审查、验收或规则检查。
7. **可观测能力**：执行过程、日志、指标、结论应可追踪。
8. **人工干预能力**：允许用户在关键环节中止、修正、批准或重规划。

## 4. Agent 资产层边界

项目级 agent asset 位于 `.claude/agents/`，属于组织层与执行基础设施层之间的可复用配置说明。它沉淀角色用途、输入输出、工具边界、交接规则和禁止事项，但不直接执行任务，也不替代 `src/opc/roles.py` 中的 runtime agent 实现。

| 对象 | 边界 |
| --- | --- |
| Claude skill | 可被 Claude Code 调用的协作能力，适合模板生成、评审、发布检查等行为 |
| Agent asset | 可复用角色/任务配置文档，描述角色边界和工具约束，不直接运行 |
| Runtime agent | OPC workflow 中真实执行的 agent prompt、工具配置和阶段逻辑 |
| Workflow pack | 一类任务的流程、权限、角色、验收和 trace 规范，可引用 skill 或 runtime agent |

Agent asset 的维护原则是“当前 runtime 事实优先”：当代码中的角色 prompt、工具权限或 workflow 边界发生变化时，asset 必须同步更新；当 asset 与当前代码冲突时，不得把 asset 当作运行时事实。

## 5. Run Trace Schema

OPC 的运行记录存放在项目 `artifacts/` 目录，第一版 schema 面向只读复盘与兼容读取：

| 文件 | 用途 | 兼容要求 |
| --- | --- | --- |
| `run_events.jsonl` | append-only 事件流，记录 stage、tool、guardrail 等过程事件 | 新读取逻辑优先使用该文件重建事件 |
| `run_trace.json` | 单次 run 的完整快照，包含 `trace_schema_version`、`run_id`、`final_status`、`metrics`、`events` | 缺少 `trace_schema_version` 的旧文件按 version 0 读取 |
| `run_metrics.json` | token、耗时、工具调用、质量指标等聚合结果 | trace 缺少 metrics 时可回退读取该文件 |

当前 schema version 为 `1`。新增字段必须保持向后兼容：旧 trace 缺字段时使用空指标、空事件或未知状态，不阻断 `opc runs list`、`opc trace summary`、`opc trace show` 等只读命令。

## 6. 权限 Profile 与危险操作策略

OPC P6 第一版采用开发友好的默认策略，但危险操作不直接执行：

| Profile | 可见工具权限 | 用途 |
| --- | --- | --- |
| `read-only` | `read` | review、诊断、只读 trace inspect |
| `write` | `read`、`write` | 文档或代码编辑，不允许执行命令 |
| `execute` | `read`、`write`、`execute` | 默认本地开发闭环，可运行定向测试 |
| `dangerous` | `read`、`write`、`execute` | 仅表示允许声明高风险意图，危险命令仍受策略控制 |

危险命令策略通过 `dangerous_command_policy` 表达：

| 策略 | 行为 |
| --- | --- |
| `allow` | 读操作和已授权低风险操作直接允许 |
| `deny` | 默认危险命令策略，直接返回 `guardrail_blocked` |
| `approval` | 发布、强推、外部影响动作返回 `approval_required`，不继续执行 |
| `audit` | 记录 `guardrail_warning` 后允许继续执行 |
| `stop` | 工具定义非法、超硬限制或运行时熔断时停止 workflow |

危险命令包括 `git push --force`、`git reset --hard`、`git clean -f`、`npm publish` 等模式。发布、强推、删除、外部影响动作默认应保持 deny 或 approval，不作为普通 execute 工具直接运行。

## 7. 插件与 MCP 接入安全契约

插件默认禁用：`opc_plugins/` 中的 Python 模块只有在同目录 `opc-plugin.toml` 中声明后才加载。manifest 最小结构：

```toml
[[plugin]]
module = "hello_plugin.py"
description = "Read-only sample plugin."
permissions = ["read"]
```

加载约束：

- 未出现在 manifest 中的模块不加载。
- 未声明 `permissions` 的模块不加载。
- 插件注册的工具权限必须包含在 manifest permissions 中，否则注册结果会被移除。
- 插件工具仍受 permission profile 与危险命令策略约束。

MCP 接入暂不在 P6 内直接实现。后续接入时必须复用同一安全契约：服务 manifest、权限声明、默认禁用、审计信息可见、外部出域动作默认 approval。

### 7.1 Project Type / Plugin Pack 架构边界

P9 起，项目生成能力按 project type 组织，核心 runtime 只负责发现、校验、路由和 trace，不直接内置 Qt、Python、Node、Rust 或 Embedded 的具体生成逻辑。

| 对象 | 职责边界 | 不应承担的职责 |
| --- | --- | --- |
| Project type | 声明项目类型 id、展示名、模板入口、环境检查、构建命令、验收检查和权限需求 | 不直接执行模板渲染、shell 命令或外部安装 |
| Plugin pack | 通过 manifest 注册一个或多个 project type、tool provider 或 workflow pack，默认禁用并按配置启用 | 不绕过 permission profile、危险命令策略或 manifest 权限声明 |
| Template pack | 提供版本化模板目录、模板变量 schema、文件清单和安全渲染规则 | 不在渲染阶段调用模型生成关键构建文件 |
| Tool provider | 提供环境检测、构建检测或诊断工具，例如 CMake/Qt 检查 | 不在未启用对应 plugin pack 时主动运行 |

Qt 第一版作为 `qt` project type 进入可选 plugin pack，模板限定为 Qt 5.14.2 Widgets + CMake。核心 runtime 不依赖 Qt SDK、CMake 或 Qt 模板目录；只有用户启用 Qt plugin pack 或显式调用 Qt 生成/检查命令时，才加载 Qt manifest、模板 pack 和 Qt tool provider。

同一机制应能复用到后续项目类型：Python project type 可声明虚拟环境与测试命令，Node project type 可声明 package manager 与 build script，Rust project type 可声明 cargo 检查，Embedded project type 可声明工具链与烧录前检查。差异应体现在 manifest、template pack 和 tool provider 中，而不是扩散到核心 workflow 控制流。

## 8. OPC Harness L1-L6 能力矩阵

| 层级 | OPC 当前能力 | P6 处理结论 |
| --- | --- | --- |
| L1 信息边界 | `ROLE_CONTEXT_SECTIONS` 按角色裁剪 ContextPack，RAG 来源通过 `context_sources` 标注 | 产品化为上下文治理契约，不复制宽泛 super-agent 上下文 |
| L2 工具系统 | ToolDefinition 声明 permission、side_effect、timeout，支持 profile 过滤 | 已具备基础能力，P6 加强权限 profile 与插件 manifest |
| L3 执行编排 | PM → Engineer → QA 主链路，动态 Architect/Ops/Growth，run trace 记录阶段事件 | 保持 MVP 工作流，完整 DAG 作为 P6/P7 分步增强 |
| L4 记忆与状态 | WorkingMemory、workflow state、artifacts、run trace 分离 | 明确 run 状态不写入长期 memory，长期写入需确认 |
| L5 评估与观测 | run_metrics、run_events、run_trace、QA 输出 schema | P6 增加 CLI inspect/trace 查看与 golden 样例 |
| L6 约束校验与恢复 | schema 校验、max rounds、dangerous command guardrail、resume | 加强 GuardrailPolicy、审批事件、失败分支记录 |

结论：OPC 已具备 harness 的主干骨架，P6 重点是把已有能力产品化和可验证化；暂不复制 DeerFlow 的宽 agent 编排、长期自治 memory 或服务化控制面。

## 9. 信息边界与上下文治理契约

- 角色只能看到 `ROLE_CONTEXT_SECTIONS` allowlist 中的 ContextPack 字段。
- RAG、impact analyzer、stage summary 等外部上下文必须进入 `context_sources`，禁止无来源注入事实。
- 当前文件事实优先于 memory、历史摘要和 RAG；若冲突，必须重新读取当前文件或标记冲突。
- memory 只能作为候选上下文，不能全量注入 prompt，也不能覆盖当前 workspace 中可验证事实。
- 禁止注入内容：凭证、`.env`、未授权外部数据、一次性调试日志、无来源长历史全文。

## 10. 单人本地运行边界

OPC v1 的运行边界是本地单人 harness，不是团队工作台或服务端控制面：

| 运行对象 | 本地单人边界 | 不进入 v1 的能力 |
| --- | --- | --- |
| 配置 | `opc.toml`、环境变量和本地 profile 只服务当前操作者 | 组织级配置下发、多人配置继承 |
| 权限 | permission profile 与 dangerous policy 保护本机工具调用 | 团队 RBAC、远端审批人、跨用户授权 |
| Trace / Audit | run trace、tool audit 和 metrics 写入本地 artifacts | 中心化审计平台、跨项目问责报表 |
| Memory | 长期 memory 需有明确 scope、来源和确认语义 | 自动沉淀全部对话、团队共享长期记忆 |
| Run 状态 | checkpoint 和 artifact 只恢复当前项目的一次执行链路 | 多人并发锁、分布式队列、远端 checkpoint |
| 数据 | 客户代码、索引、日志和产物默认留在本机目录 | 默认上传云端、托管数据库、多租户存储 |

因此，P7 的改进优先围绕本地项目 registry、run 冲突提示、memory 生命周期、数据清理/备份和只读审计导出展开；团队治理、多用户模式和服务化部署需要单独立项，不应混入 v1 默认承诺。

## 11. 部署运维与私有化运行边界

P6 后 OPC 的可运行形态分为三类，当前只承诺本地 CLI 与容器化 CLI 边界，不把服务端控制面作为近期交付：

| 模式 | 适用能力 | 数据与日志 | 升级/回滚边界 | 不适合承诺的能力 |
| --- | --- | --- | --- | --- |
| 本地单机 CLI | `opc init/doctor/run/resume/runs/trace/index/query`，单人项目交付闭环 | 保存在本机 workspace、artifacts、索引目录和环境变量中 | 通过包版本、git 状态和本地备份回滚 | 长期后台任务、共享审批、远端同步 |
| 容器化 CLI | 用 Docker 镜像复现 CLI 运行环境，适合 CI 或隔离执行一次性命令 | 需要显式挂载 workspace、配置、索引和 secret；容器内临时文件不视为持久状态 | 通过镜像 tag 与挂载目录备份回滚 | 默认常驻服务、自动备份、托管 secret |
| 私有持久服务 | 需要额外 server/control plane 才能支撑队列、后台运行、集中审计和多人审批 | 需要数据库、对象存储、日志保留、备份、权限和删除策略 | 需要迁移、灰度、回滚和运维手册 | 不进入 P6/v1 默认范围 |

运维结论：适合本地 CLI 的能力继续围绕可诊断、可回放、可清理展开；需要 server/control plane 的能力必须单独设计资源、数据、日志、备份、升级、回滚和权限模型；私有化部署不能只靠当前 Dockerfile 宣称完成。

## 12. 合规与数据边界清单

| 数据/动作 | 会被读取 | 会被存储 | 可能出域 | 保留/删除边界 |
| --- | --- | --- | --- | --- |
| 敏感数据 | 只有用户任务、工具或检索范围显式触达时读取 | 不应写入长期 memory；trace 中只保留必要诊断摘要 | 仅在模型上下文或外部工具调用需要时，且必须受权限/来源约束 | P7 需补敏感扫描、redaction 和清理命令 |
| 密钥/API Key | 通过环境变量或 secret provider 注入 | 禁止写入 `opc.toml`、版本控制文件、memory 和 artifact | 不应作为 prompt、RAG chunk 或插件参数出域 | `.env` 写入默认阻止，泄露时由用户轮换密钥 |
| 客户代码 | workflow、RAG、工具调用会读取授权 workspace 内文件 | 索引、trace、artifact 默认保存在本机 | 调用模型、MCP 或插件时可能进入外部处理链路 | 用户可通过删除 workspace/artifacts/index 清理本地副本 |
| 日志与 trace | 工具调用、阶段输出、guardrail 事件会被记录 | `run_events.jsonl`、`run_trace.json`、`run_metrics.json` | 默认不上传；外部审计导出需用户显式触发 | P6 默认本地保留，P7 补按 run/project 清理策略 |
| 外部工具出域 | 插件、MCP、shell、API 调用可能出域 | 记录工具名、参数摘要、权限和结果摘要 | 需要 manifest、permission profile 和 approval/deny 策略约束 | 未声明权限的插件不加载，MCP 接入前保持默认禁用 |
| Memory | 只读取与任务、角色、scope 匹配且未过期的长期事实 | 用户偏好、项目决策、外部引用可长期保存 | 不自动发送全量 memory，只注入必要片段与来源 | 关键长期写入需确认，P7 补删除、更新和 supersede 路径 |
| 审计保留 | 本地审计用于复盘、失败定位和安全检查 | 归属本地操作者，不作为团队问责系统 | 默认不出域；导出需用户显式命令 | P7 补只读导出、保留期和清理策略 |

## 13. Memory 分层与生命周期规范

Memory 与 RAG、Session、Checkpoint、Artifact 分工不同：RAG 定位当前项目知识，Session 只是一次 CLI/IDE 交互过程，Checkpoint 只服务 `opc resume`，Artifact 是 run 证据；Memory 只保存经过确认、可跨任务复用的事实或偏好。

| Scope | 内容 | 生命周期 | 写入边界 |
| --- | --- | --- | --- |
| `user` | 用户偏好、协作方式、长期目标 | 默认长期，需支持 supersede/delete | 写入前需要确认，禁止凭证和临时调试状态 |
| `project` | 项目决策、约束、外部引用 | 随项目有效，过期或冲突时 supersede | 写入前需要确认，当前文件事实优先 |
| `workflow` | 可复用 workflow pack 经验、角色边界 | 随 workflow 规范有效 | 需要来源和置信度，不能来自单次失败日志自动沉淀 |
| `run` | 单次 run 的阶段状态、失败点、审批记录 | 只保存在 trace/state，不进入长期 memory | 不允许提升为长期 memory，除非人工改写为项目决策 |
| `artifact` | PRD、实现说明、QA 报告、metrics | 作为本地 artifact 保留 | 只作为证据引用，不整篇写入长期 memory |

每条结构化 memory 至少包含 `scope`、`created_at`、`updated_at`、`expires_at`、`source`、`confidence`。过期 memory 不注入上下文；被替代的 memory 必须通过 `superseded_by` 或后续删除路径标记。短期 run 状态、tool 输出、trace 事件和 artifact 全文默认只留在 artifacts，不自动写入长期 memory。

Memory 检索注入策略：按任务、角色和 scope 只选择未过期的 `user/project/workflow` 长期事实；`run/artifact` scope 只能作为 trace 或证据引用，不作为 prompt memory 注入。注入时必须写入 `context_sources`，包含 memory id、scope、role、status 和 reason；如果 memory 与当前 workspace 文件事实、stage summary 或 ContextPack facts 冲突，当前事实优先，memory 标记为 `conflict_current_fact` 后不注入。Memory 不允许全量注入 prompt，也不能绕过 `ROLE_CONTEXT_SECTIONS` 的角色可见字段。

Memory 写入审核与安全边界：长期 `user/project/workflow` memory 写入默认返回 `review`，只有确认后才允许 `write`；`run/artifact`、凭证、`.env`、API key、token、password、private key、临时调试状态和 trace 片段默认 `reject`，不提升为长期 memory。删除和 supersede 也必须走确认路径，并产生 `memory_write_policy` 审计事件，记录 action、reason、scope 与 source；旧 memory 被替代时必须写入 `superseded_by`，而不是静默覆盖。

默认原则：当前 workspace 文件事实优先；凭证、临时调试内容、无来源长历史全文和未授权外部数据不得进入长期 memory；任何外部工具、插件或 MCP 出域动作都必须能在 trace/audit 中定位来源和权限原因。
