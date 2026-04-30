# OPC-Harness

> A Harness Engineering framework for building one-person software companies with AI agents

## 项目定位

OPC-Harness 是一个面向"单人软件公司"的 AI 操作系统，通过 Harness Engineering 方法论，将产品、架构、研发、测试、运维、增长等职责拆分为可协作的 AI Agent 角色，形成可计划、可执行、可验证、可干预的软件生产体系。

**核心理念：** 不追求"更聪明"的 Agent，而是构建"更可靠"的 Agent 公司系统。

## 核心特性

- **多角色协作体系**：CEO、PM、Architect、Engineer、QA、Ops、Growth 等角色明确分工
- **Harness 工作流**：任务拆解 → 执行 → 验证 → 反馈的完整闭环
- **结构化产出**：PRD、架构文档、任务清单、验收文档等标准化交付物
- **人工监督节点**：关键决策点支持人工确认、拒绝、回滚
- **记忆与上下文管理**：基于 BM25 的 RAG 检索，支持长期记忆
- **工具链集成**：文件操作、Shell 执行、代码分析等嵌入式开发工具

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

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 ANTHROPIC_API_KEY
```

### 基础使用

```python
from src.opc import OPC

# 初始化 OPC 实例
opc = OPC()

# 运行任务
result = opc.run("帮我设计一个用户登录功能")
print(result)
```

### 交互式模式

```bash
python run_opc.py
```

## 项目结构

```
OPC-Harness/
├── src/                    # 核心代码
│   ├── opc.py             # OPC 主入口
│   ├── roles/             # 角色定义（CEO、PM、Architect 等）
│   ├── tools/             # 工具集（文件、Shell、代码分析）
│   ├── memory/            # 记忆系统（BM25 RAG）
│   └── environment/       # 执行环境
├── workspace/             # 工作空间（任务产出）
├── test_data/             # 测试数据
├── CLAUDE.md              # Claude 协作规范
└── README.md              # 本文件
```
├── test_data/             # 测试数据
├── CLAUDE.md              # Claude 协作规范入口
└── README.md              # 本文件
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

### 场景 1：需求到实现的完整流程

```python
# 1. CEO 确定目标
opc.run_as_role("CEO", "我们需要一个用户认证系统")

# 2. PM 编写 PRD
opc.run_as_role("PM", "基于 CEO 的目标，编写用户认证系统的 PRD")

# 3. Architect 设计架构
opc.run_as_role("Architect", "基于 PRD，设计认证系统的技术架构")

# 4. Engineer 实现代码
opc.run_as_role("Engineer", "基于架构文档，实现用户登录功能")

# 5. QA 验证功能
opc.run_as_role("QA", "验证登录功能是否符合 PRD 要求")
```

### 场景 2：嵌入式开发辅助

```python
# 使用嵌入式工具链
opc.run_with_tools([
    "read_file",      # 读取代码文件
    "write_file",     # 写入代码文件
    "execute_shell",  # 执行编译命令
    "analyze_code"    # 分析代码结构
], "帮我优化这段 C++ 代码的性能")
```

### 场景 3：基于记忆的上下文检索

```python
# 保存项目知识
opc.memory.add("用户认证采用 JWT 方案")

# 后续任务自动检索相关上下文
opc.run("实现用户登出功能")  # 自动检索到 JWT 相关信息
```

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
