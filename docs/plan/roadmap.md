# 路线图、MVP 范围与风险

## 1. 对标开源项目与借鉴点

本项目不从零定义所有概念，而是吸收已有开源项目的组织方式与技术经验。

| 参考项目/方向 | 借鉴点 |
| --- | --- |
| MetaGPT | 多角色协作、角色分工、文档驱动的软件流程 |
| OpenHands / OpenDevin | 面向真实开发任务的 Agent 执行方式 |
| OpenHarness | 工具封装、技能体系、执行环境抽象 |
| AutoGen / LangGraph | 多 Agent 编排、状态流转、节点化执行 |
| Anthropic Agent Workflow | Planner / Generator / Evaluator 式闭环思想 |
| Harness 类工程理念 | 验证、权限、可观测、人工介入与持续优化 |

原则上，本项目借鉴这些项目的"组织结构与方法"，但不机械复制其实现细节。

## 2. MVP 边界

MVP 的目标不是一次做完完整公司，而是先跑通最关键的一条交付链路。

### 2.1 最小可验证交付闭环

MVP 默认闭环为 **PM → Engineer → QA**：

| 环节 | 输入 | 输出 | 验收标准 | 失败路径 |
| --- | --- | --- | --- | --- |
| PM | 用户目标、约束、上下文 | 结构化 PRD、范围、验收标准 | goal、scope、non_goals、acceptance_criteria 清晰可检查 | 需求不清时退回用户或 PM 重新澄清 |
| Engineer | PM 输出、代码上下文、QA 返工意见 | 代码变更、实现摘要、验证结果 | 变更可定位、验证可复现、失败原因可说明 | 实现失败时终止或进入人工介入；QA 失败时带 defects 回流 |
| QA | PM 验收标准、Engineer 输出、验证证据 | pass/fail、checked_items、evidence、defects、next_action | 结论明确，证据与验收标准对应 | fail 回流 Engineer；标准冲突时升级 PM 或用户 |

### 2.2 动态多角色入口

MVP 保留 Architect、Ops、Growth 等动态角色入口，但默认不把它们放入主链路：

- Architect：仅在方案边界、接口设计或技术取舍不清时激活。
- Ops：仅在任务涉及运行环境、部署、回滚或监控时激活。
- Growth：仅在任务涉及用户获取、转化或指标分析时激活。
- CEO / 用户：仅在目标、优先级或高风险动作需要决策时介入。

动态角色的输出必须回到 PM、Engineer 或 QA 的主链路产物中，不能形成绕开最小闭环的独立交付路径。

### 2.3 MVP 必须覆盖的能力

- 至少 3 个角色可以协作：PM、Engineer、QA
- 具备最小任务拆解能力
- 可调用最基本工具：文档、代码编辑、终端执行
- 能完成一次从需求到实现到验证的闭环
- 有最小的项目规范文档与角色协作规则

### 2.4 MVP 暂不覆盖的能力

- 复杂自治调度系统
- 大规模并行多 Agent 运行
- 完整企业级监控平台
- 高复杂度记忆检索系统
- 全自动商业增长系统

### 2.5 Roadmap 中的 OS 级能力

以下能力不计入 MVP 当前能力，只作为后续产品化路线：

| 能力 | 当前状态 | 进入 Roadmap 的原因 |
| --- | --- | --- |
| 资源调度 | Planned | 目前没有独立调度器、队列优先级或资源配额实现 |
| 权限隔离 | Planned | 目前只有工具白名单和工作目录约束，尚未形成沙箱级隔离 |
| 进程管理 | Planned | 当前工作流同步执行，不托管长生命周期进程 |
| 多租户 | Planned | 当前状态、索引和 artifacts 面向本地单项目使用 |
| 自定义 workflow 引擎 | Planned | 当前只保留最小声明式流转方向，尚未支持完整 roles/steps/transitions 配置 |
| 完整中断恢复 | Experimental | 已有 run state 与 trace 基础，但消息、工具结果和运行中进程恢复仍未闭环 |

README 中涉及这些能力时，应使用 Roadmap 或 Experimental 表述，不能作为当前可用能力承诺。

## 3. 分阶段路线图

### Phase 1：跑通最小闭环

目标：完成"需求 → 任务 → 实现 → 验证"的最小链路。

重点事项：

- 确立角色定义与基础文档模板
- 明确项目级 Claude/Agent 协作规范
- 选择最小可用的工具执行方式
- 完成一个演示型软件任务闭环

### Phase 2：增强角色协作

目标：让角色分工更清晰，任务交接更稳定。

重点事项：

- 增加 Architect 角色
- 建立任务输入输出模板
- 强化验收标准与回退机制
- 建立角色间的协作协议

### Phase 3：引入运维与观测

目标：让系统具备可发布、可追踪、可复盘能力。

重点事项：

- 建立发布与回滚流程
- 定义关键运行指标
- 保留执行日志与结果记录
- 建立问题复盘机制

### Phase 4：形成可扩展公司框架

目标：从单次任务系统升级为可持续运行的单人软件公司框架。

重点事项：

- 增加 Growth / Research 角色
- 引入更系统化的记忆与经验沉淀
- 优化任务模板、角色模板与评估标准
- 逐步支持更多项目类型

## 4. 风险、约束与关键决策

### 4.1 关键风险

| 风险 | 说明 | 应对方式 |
| --- | --- | --- |
| 角色边界模糊 | Agent 容易越权或职责重叠 | 强制定义输入输出和责任归属 |
| 任务拆解不稳定 | 高层需求难以直接落地 | 先缩小任务范围，强化 PRD 与验收标准 |
| 工具调用不可控 | 高风险操作可能破坏环境 | 设置权限边界与人工审批节点 |
| 结果验证不足 | 生成内容可能表面正确、实际不可用 | 强制测试、审查与验收闭环 |
| 上下文丢失 | 多轮执行后信息不一致 | 依赖文档、记忆与状态记录维持一致性 |
| 过度设计 | 过早构建复杂平台 | 坚持 MVP 优先，按阶段扩张 |

### 4.2 当前关键约束

- 项目目前以文档与方法论重构为起点
- 需要优先建立统一术语与角色体系
- 需要先定义协作规则，再开展后续工程实现
- 需要让文档本身可直接指导 Claude / Agent 工作

### 4.3 当前关键决策

1. 以 Harness Engineering 作为项目方法论总纲。
2. 以"单人软件公司操作系统"作为项目定位。
3. 采用"组织层 + 执行基础设施层 + 评估运维闭环层"的三层架构。
4. MVP 优先追求最小闭环，而不是最大功能覆盖。

## 5. OPC v1 单人本地使用边界

P6 后 OPC v1 继续保持 **单人本地优先**：默认服务对象是一个独立开发者在本机、单 workspace、单账号上下文中完成软件交付闭环。团队协作、多用户权限、中心化控制面和托管服务不进入 v1 近期范围，避免把 harness 使用层误扩展成团队平台。

| 边界项 | v1 结论 | P7 候选补齐方向 |
| --- | --- | --- |
| 项目切换 | 通过 `--project`、`--project-dir`、workspace 目录和本地 artifacts 区分项目，不提供跨用户项目空间 | 增加本地项目 registry、最近 run 索引和项目级默认 profile |
| 权限默认值 | 默认采用开发友好的 `execute` profile，危险操作仍由 `dangerous_command_policy=deny` 阻断 | 增加按项目持久化 profile、首次运行权限提示和配置漂移检查 |
| 审计归属 | audit、trace、metrics 均归属本地操作者本人，用于复盘而非团队问责 | 增加本地审计导出、run 标签和按项目归档策略 |
| 本地 memory | 长期 memory 仅记录经确认的偏好、项目决策和外部引用，不写入一次性 run 状态 | 增加 memory scope、过期、删除、supersede 和写入审核路径 |
| Run 冲突处理 | 同一项目可产生多个 run artifacts，但不提供并发锁、多人抢占或远端同步 | 增加本地运行锁、重复 run 提示和失败 resume 选择器 |
| 数据存储 | `workspace/`、`artifacts/`、索引目录和配置文件保存在本机文件系统 | 增加数据目录体检、备份/清理命令和敏感文件扫描 |

近期不做项：团队成员管理、组织级 RBAC、共享审批队列、远端 trace 聚合、托管数据库、多租户隔离和服务端控制面。这些能力只有在本地单人闭环稳定、评测基准可复现后，才作为独立产品阶段重新评审。

## 6. 功能增强路线图（Todolist）

> 目标：补齐 OPC 作为“一人成一个开发组”所需的关键能力，优先让需求定义、任务执行、验收、成本观测和知识复用形成闭环。

### P0 - 先补最直接提升交付质量的能力

- [ ] 新增 `bugfix` skill：把缺陷描述转成根因分析、最小修复和定向验证。
- [ ] 新增 `test-spec` skill：把需求或缺陷转成可执行测试点与测试用例。
- [ ] 新增 `implementation-check` skill：对照 task-spec / PRD / 架构做实现自检。
- [ ] 新增 `token-report` skill：基于 run metrics 输出 token、API 调用和耗时报告。
- [ ] 让每次 run 都记录更完整的 token / model / cost 数据，便于后续统计和趋势分析。

### P1 - 再补流程化与可复用能力

- [ ] 增加 `review` / `release-check` / `ops-check` 类 skill，让评审与发布检查标准化。
- [ ] 落地 workflow pack / manifest 目录，统一定义 id、kind、owner_roles、inputs、outputs、permissions、acceptance、trace。
- [ ] 细化可选角色的启用规则，让 Architect / Ops / Growth 的触发条件更明确、可配置、可解释。
- [ ] 增加统一的 `scripts/` 目录，收拢 run、check、review、cost 等命令入口。
- [ ] 补充更明确的 agent 资产层，让可复用 agent 定义从 runtime 代码中分离出来。

### P2 - 最后补知识沉淀与长期观测

- [ ] 增强知识检索与上下文复用，把任务结果、验证证据和复盘结论更系统地回流到 memory 与索引。
- [ ] 提供 token / cost 的趋势分析，定位最耗资源的角色、阶段和任务类型。
- [ ] 增加更完整的质量门禁，覆盖实现自检、QA 前检查和发布前检查。
- [ ] 建立更系统的脚本与文档索引，降低新入口、skills 和 workflow pack 的查找成本。

## 7. 部署与私有化 Roadmap 边界

| 能力 | 近期定位 | Roadmap 结论 |
| --- | --- | --- |
| 本地单机 CLI | v1 主要运行方式 | 继续补 doctor、trace inspect、数据清理、备份提示和本地权限默认值 |
| Docker CLI 镜像 | 环境复现与一次性命令执行 | 保持 `ENTRYPOINT ["opc"]`，要求用户显式挂载 workspace、索引目录和 secret |
| 持久后台服务 | 需要 server/control plane | 暂不进入近期 Roadmap，需另行设计队列、进程托管、日志保留和升级回滚 |
| 私有化部署 | 只有在服务端能力立项后评估 | 需要数据库、对象存储、权限、审计、备份、删除和迁移方案，不由当前 Dockerfile 直接承诺 |

P7 若继续推进部署运维，优先补本地 CLI 体检、run/artifact 清理、只读审计导出和 Docker 使用说明；不要把当前镜像误标为可长期运行的企业私有部署。

## 8. P10 工业级本地产品底座边界

P10 的“工业级落地”只收敛本地单人 CLI 产品底座：可持续交付、可诊断、可治理、可发布。近期目标是让单人操作者能在本机完成 release gate、自查 artifacts/index、轻量 workflow pack 发现/smoke、插件安全校验、RAG golden eval 和文档入口定位。

近期非目标：团队平台、常驻服务、多租户、企业私有化控制面、共享审批队列、托管数据库、远端 trace 聚合和自动发布系统。出现这些需求时，应作为独立产品阶段重新评审，而不是在 P10 中隐式承诺。

### 8.1 Release gate

| 检查项 | 本地入口 | 阻塞规则 | 补验条件 |
| --- | --- | --- | --- |
| CI / 定向测试 | `python -m pytest ...`、CI workflow | 已声明 must-pass 的测试失败即阻塞 | 完整矩阵由 CI 补验 |
| 覆盖率 | CI 覆盖率或定向覆盖说明 | 覆盖率门禁失败阻塞；未配置时记录 needs-env | CI 环境补证 |
| CLI smoke | `tests/test_cli_smoke.py` | CLI 解析/只读命令失败阻塞 | 无 |
| Docker build/smoke | Docker workflow / 目标环境 | 有 Docker 环境失败阻塞；无 Docker 记录 skip | Docker 目标环境补验 |
| Artifact 兼容 | `opc artifacts doctor` | schema 损坏或关键 JSON 无法读取阻塞 | 旧 trace 缺字段可 warning |
| RAG eval | `python scripts/run-rag-eval.py` | golden eval 低于当前基线阻塞；趋势项可 warning | 大索引/向量 eval 可补验 |
| 安全扫描 | plugin/security tests、敏感文件名 doctor | 权限越界、路径越界、secret 文件名进入长期证据阻塞 | 外部 SAST 可补验 |
| 文档索引 | README、DOCS_STRUCTURE、workflow pack README | 新入口不可发现时阻塞发布 | 链接检查可补验 |

`python scripts/check-release.py` 生成本地 release report，只写报告文件，不执行发布、上传、push、删除或重型全量命令。

### 8.2 Artifacts / Index / Memory 数据治理

- `artifacts/` 保留 run 证据、trace、metrics、state、角色输出和生成摘要；清理前必须能说明不会影响 resume、验收或审计。
- index 目录是本地可重建缓存；可清理但必须先 dry-run 列出索引名、路径、体积、风险和重建影响。
- memory 只保存已确认的长期偏好、项目决策和外部引用；禁止把 `.env`、API key、token、password、private key、临时调试内容、run trace 片段写入长期 memory。
- doctor/cleanup 入口只做本地只读扫描或 dry-run，不上传内容，不默认删除用户数据。

### 8.3 Workflow pack runtime 化决策

| Pack | kind | 近期入口 | 权限 | 产物 / Trace | P10 结论 |
| --- | --- | --- | --- | --- | --- |
| `bugfix` | `opc_runtime_workflow` | `opc run` | read/write/execute 定向验证 | run trace、修复摘要、测试证据 | 保持 runtime 候选 |
| `docs-update` | `opc_runtime_workflow` | `opc workflow-packs smoke --id docs-update` / `opc run` | 文档写入、文档检查 | `workflow_pack_smoke.json`、run trace | 作为低风险 runtime smoke |
| `review` | `claude_skill` | `/review` | read | review 报告 | 保持 skill |
| `release-check` | `claude_skill` + script | `/release-check`、`scripts/check-release.py` | read/report write | release report | 不自动发布 |
| `qt-generation` | `opc_runtime_workflow` | `opc generate qt` | template write、可选环境检查 | `qt_generation.json`、run trace | 保持可选插件 runtime |

### 8.4 插件与供应链治理

内置插件、仓库插件、外部插件按信任等级区分。内置和仓库插件仍需 manifest；外部插件默认不加载。Project type manifest 必须位于项目根内，字段必须在白名单内，权限只能是 `read/write/execute`，重复 id 或路径越界直接拒绝。后续若引入 hash/签名，release gate 应把缺失签名列为 warning 或阻塞项，取决于插件来源。

### 8.5 RAG golden eval

RAG golden eval 使用 `tests/fixtures/rag_eval_dataset.json` 作为小数据集，覆盖中文问题、英文代码符号、文档章节、插件/Qt 问题和误召回诊断。默认入口 `scripts/run-rag-eval.py` 使用内存 BM25 小语料输出 top-k、hit/miss、MRR、NDCG 和失败原因，不调用 LLM，不重建大型向量索引。
