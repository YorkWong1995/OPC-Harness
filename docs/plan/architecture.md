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

## 4. Run Trace Schema

OPC 的运行记录存放在项目 `artifacts/` 目录，第一版 schema 面向只读复盘与兼容读取：

| 文件 | 用途 | 兼容要求 |
| --- | --- | --- |
| `run_events.jsonl` | append-only 事件流，记录 stage、tool、guardrail 等过程事件 | 新读取逻辑优先使用该文件重建事件 |
| `run_trace.json` | 单次 run 的完整快照，包含 `trace_schema_version`、`run_id`、`final_status`、`metrics`、`events` | 缺少 `trace_schema_version` 的旧文件按 version 0 读取 |
| `run_metrics.json` | token、耗时、工具调用、质量指标等聚合结果 | trace 缺少 metrics 时可回退读取该文件 |

当前 schema version 为 `1`。新增字段必须保持向后兼容：旧 trace 缺字段时使用空指标、空事件或未知状态，不阻断 `opc runs list`、`opc trace summary`、`opc trace show` 等只读命令。

## 5. 权限 Profile 与危险操作策略

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
| `deny` | 默认策略，直接返回 `guardrail_blocked` |
| `approval` | 返回 `approval_required`，不继续执行 |
| `audit` | 记录 `guardrail_warning` 后允许继续执行 |

危险命令包括 `git push --force`、`git reset --hard`、`git clean -f`、`npm publish` 等模式。发布、强推、删除、外部影响动作默认应保持 deny 或 approval，不作为普通 execute 工具直接运行。

## 6. 插件与 MCP 接入安全契约

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
