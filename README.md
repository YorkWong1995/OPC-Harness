# OPC

> A Harness Engineering framework for orchestrating one-person software delivery with AI agents

## 项目定位

OPC 是一个面向"单人软件公司"的软件交付编排层。它通过 Harness Engineering 方法论，将产品、架构、研发、测试、运维、增长等职责拆分为可协作的 AI Agent 角色，形成可计划、可执行、可验证、可干预的软件生产体系。

"操作系统"是 OPC 的长期隐喻和远期愿景；当前阶段的核心能力，是围绕软件交付流程提供角色协作、工作流约束、可观测记录和人工介入边界。

**核心理念：** 不追求"更聪明"的 Agent，而是构建"更可靠"的 Agent 公司系统。

## 核心特性

OPC 按严格标准标注能力状态：有代码、有测试、可本地复现的能力标为 **Available**；已有部分实现但仍在收敛的能力标为 **Experimental**；尚未完整实现的能力标为 **Planned / Roadmap**。

| 状态 | 能力 | 说明 |
| --- | --- | --- |
| Available | PM → Engineer → QA 最小工作流 | 支持结构化需求、实现、验收、QA 退回与轮次限制 |
| Available | 结构化角色输出 | PM、Engineer、QA 具备 schema 校验与契约测试 |
| Available | Run trace 与基础指标 | 记录 workflow state、events、role outputs、token 用量和 API 调用次数 |
| Available | 知识索引与检索 | 支持 `opc index`、`opc query` 和 BM25/向量混合检索 |
| Experimental | 动态多角色入口 | Architect、Ops、Growth 可按任务或配置启用，但不作为默认主链路 |
| Experimental | 工具链集成 | 文件操作、Shell 执行、代码分析等工具可用，协议、安全和审计仍在收敛 |
| Planned / Roadmap | OS 级运行时能力 | 资源调度、权限隔离、进程管理、多租户、自定义 workflow、完整恢复入口等进入 Roadmap |

## 快速开始

### 环境要求

- Python 3.8+
- Anthropic API Key（Claude 模型）

### 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/OPC-Harness.git
cd OPC-Harness

# 安装依赖
pip install -e .

# 如需中英混合/中文场景的 BGE 向量嵌入支持
pip install -e .[bge]

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 ANTHROPIC_API_KEY
```

### 基础使用

```bash
# 在当前目录运行最小 harness 工作流
opc run "帮我设计一个用户登录功能"

# 指定 workspace/ 下的项目目录
opc run "帮我设计一个用户登录功能" --project demo-login

# 指定已有项目目录，并跳过 Architect 环节
opc run "补充登录功能验收标准" --project-dir . --skip-architect
```

当前公开入口以 CLI 为主；Python 包入口仅暴露版本信息，暂不提供 `OPC()`、`run_as_role()`、`run_with_tools()` 等高级 API。

### 最小可运行示例

仓库提供一个安全的 Quickstart 脚本，默认只打印将要执行的命令，不会调用 API 或修改 workspace：

```bash
python examples/quickstart_minimal.py
```

确认命令无误后，可以用 `--execute` 触发当前可用的 PM → Engineer → QA 工作流：

```bash
python examples/quickstart_minimal.py --execute --auto-confirm
```

### 知识索引与检索

```bash
# 构建知识索引（索引指定目录下的文件）
opc index --name myproject --dirs src/opc

# 按扩展名过滤，仅索引 Python 和 Markdown 文件
opc index --name docs --dirs docs/ README.md --extensions .py .md

# 覆盖已有索引
opc index --name myproject --dirs src/opc --overwrite

# 检索查询（返回 top-10 结果并由 LLM 生成答案）
opc query "如何构建知识索引" --name myproject

# 仅显示检索结果，不调用 LLM
opc query "RAG 检索流程" --name myproject --no-llm

# 自定义返回数量和模型
opc query "Agent 角色定义" --name myproject --top-k 5 --model claude-sonnet-4-6

# 列出所有已有索引
opc index-list

# 删除索引
opc index-delete --name myproject
```

### 交互式模式

```bash
python run_opc.py
```

## 项目结构

```
OPC-Harness/
├── src/opc/                # 核心代码包
│   ├── __init__.py        # 包入口
│   ├── agent.py           # Agent 核心
│   ├── cli.py             # 命令行接口
│   ├── config.py          # 配置管理
│   ├── environment.py     # 执行环境
│   ├── memory.py          # 记忆系统
│   ├── rag.py             # RAG 检索
│   ├── rag_bm25.py        # BM25 RAG 实现
│   ├── roles.py           # 角色定义（CEO、PM、Architect 等）
│   ├── schema.py          # 数据模型
│   ├── store.py           # 存储后端
│   ├── workflow.py        # 工作流引擎
│   └── knowledge/         # 知识检索子系统
│       ├── bm25_index.py  # BM25 索引
│       ├── chunker.py     # 文档分块
│       ├── embedder.py    # 向量嵌入
│       ├── indexer.py     # 索引构建
│       ├── retriever.py   # 检索器
│       └── vector_store.py # 向量存储
├── tests/                  # 测试用例
├── docs/                   # 文档
│   ├── claude/            # Claude 协作规范
│   └── plan/              # 项目规划文档
├── workspace/              # 工作空间（任务产出）
├── test_data/              # 测试数据
├── run_opc.py              # 交互式运行入口
├── run_tasks.py            # 自动任务执行器
├── pyproject.toml          # 项目配置
├── opc.example.toml        # OPC 配置示例
├── CLAUDE.md               # Claude 协作规范入口
└── README.md               # 本文件
```

## 核心概念

### Harness Engineering

Harness Engineering 是本项目的核心方法论，强调：
- **结构化输入输出**：明确的任务边界与交付标准
- **角色分工**：职责清晰，避免混杂
- **执行闭环**：计划 → 执行 → 验证 → 反馈
- **人工监督**：关键节点允许人类介入
- **可观测性**：所有过程可追踪、可复盘

### 角色体系

| 角色 | 职责 | 必须产出 |
| --- | --- | --- |
| CEO | 战略决策、优先级排序 | 项目总纲、优先级矩阵 |
| PM | 需求分析、PRD 编写 | PRD 文档、验收标准 |
| Architect | 架构设计、技术选型 | 架构文档、接口定义 |
| Engineer | 代码实现、单元测试 | 可运行代码、测试用例 |
| QA | 测试验证、质量把关 | 测试报告、Bug 清单 |
| Ops | 部署运维、监控告警 | 部署文档、运维手册 |
| Growth | 数据分析、增长策略 | 数据报告、优化建议 |

## 使用场景

### 场景 1：需求到实现的最小流程

```bash
opc run "为示例项目补充用户登录功能的需求、实现和验收记录" --project demo-login --auto-confirm
```

该命令使用当前实现的 PM → Engineer → QA 工作流。Architect、Ops、Growth 等角色按配置或任务类型动态启用，不通过 `run_as_role()` 手动调用。

### 场景 2：知识索引与上下文检索

```bash
opc index --name myproject --dirs src/opc docs --extensions .py .md
opc query "PM 输出 schema 包含哪些字段" --name myproject --no-llm
```

### 场景 3：交互式运行

```bash
python run_opc.py
```

交互式入口适合逐步确认需求、方案、实现和验收；长期记忆写入与自动检索能力仍按 Roadmap 逐步收敛。

## 配置说明

### 环境变量（.env）

```bash
ANTHROPIC_API_KEY=your_api_key_here
```

### OPC 配置（opc.example.toml）

```toml
[opc]
model = "claude-opus-4"
max_tokens = 4096
temperature = 0.7

[memory]
enable_rag = true
top_k = 5
```

## 开发指南

### 添加新角色

1. 在 `src/roles/` 创建角色文件
2. 继承 `BaseRole` 类
3. 实现 `execute()` 方法
4. 在 `docs/claude/roles.md` 添加角色文档

### 添加新工具

1. 在 `src/tools/` 创建工具文件
2. 继承 `BaseTool` 类
3. 实现 `run()` 方法
4. 在工具注册表中注册

### 运行测试

```bash
# 运行所有测试
python -m pytest

# 运行特定测试
python test_message.py
python test_memory.py
python test_environment.py
```

## 路线图

- [x] 核心架构搭建
- [x] 多角色体系设计
- [x] 基础工具链集成
- [x] 记忆与 RAG 系统
- [ ] 完整工作流验证
- [ ] 性能优化与稳定性提升
- [ ] 多 Agent 协同编排
- [ ] Web UI 界面

## 贡献指南

欢迎贡献代码、文档或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [Anthropic Claude](https://www.anthropic.com/) - 核心 AI 能力
- [MetaGPT](https://github.com/geekan/MetaGPT) - 多 Agent 协作灵感
- Harness Engineering 方法论

## 联系方式

- Issues: https://github.com/YOUR_USERNAME/OPC-Harness/issues
- Discussions: https://github.com/YOUR_USERNAME/OPC-Harness/discussions

---

**注意：** 本项目当前处于 Alpha 阶段，API 可能会有变动。
