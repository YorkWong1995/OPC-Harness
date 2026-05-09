# OPC

**OPC（One Person Company）** —— 基于 Harness Engineering 的单人软件公司 AI 系统，通过 PM、Engineer、QA 等角色 Agent 的协作，实现从需求到交付的自动化闭环工作流。

## 功能特性

- **角色化 Agent 协作**：内置 PM（产品经理）、Engineer（工程师）、QA（验收审查）三个核心角色，各司其职、结构化交接
- **Harness 工作流闭环**：自动驱动「需求定义 → 工程实现 → 验收检查 → 复盘沉淀」的完整流程
- **人工审批节点**：关键环节支持人工确认，确保方向可控、风险可管
- **Artifact 产物管理**：工作流产出的 PRD、实现说明、验收记录等自动保存到 `artifacts/` 目录
- **工具调用与权限控制**：Engineer Agent 可读写文件、执行终端命令（白名单机制），QA Agent 仅只读访问
- **CLI 命令行驱动**：一条命令即可启动完整工作流

## 环境要求

- Python >= 3.10
- Anthropic API Key（用于调用 Claude 模型）

## 安装

```bash
# 克隆仓库
git clone <repository-url>
cd opc

# 安装项目（推荐开发模式）
pip install -e .
```

## 快速开始

1. **配置环境变量**

   复制 `.env.example` 为 `.env`，填入你的 Anthropic API Key：

   ```bash
   cp .env.example .env
   ```

   编辑 `.env`，设置以下变量：

   ```env
   ANTHROPIC_API_KEY=your-api-key-here
   # 可选：自定义 API 端点（支持中转地址）
   # ANTHROPIC_BASE_URL=https://your-proxy.example.com
   # 可选：指定模型（默认 claude-sonnet-4-6）
   # ANTHROPIC_MODEL=claude-sonnet-4-6
   ```

2. **运行工作流**

   ```bash
   opc run "为项目添加一个用户登录功能"
   ```

   该命令会自动执行：
   - **PM** 产出 PRD
   - **Engineer** 基于 PRD 完成实现
   - **QA** 基于验收标准检查实现结果
   - 若验收通过，**PM** 进行复盘沉淀

3. **查看产物**

   工作流运行后，所有产出文档保存在项目目录的 `artifacts/` 下：

   ```
   artifacts/
   ├── prd.md              # 需求文档
   ├── implementation.md   # 实现说明
   ├── acceptance.md       # 验收记录
   └── retrospective.md    # 复盘记录
   ```

## 用法

### 基本用法

在指定项目目录下运行任务：

```bash
opc run "为 CLI 添加一个 version 子命令"
```

### 指定项目目录

默认使用当前目录，可通过 `--project-dir` 指定：

```bash
opc run "修复 README 中的拼写错误" --project-dir /path/to/project
```

### 自动确认模式

跳过所有人工审批节点，全自动运行工作流：

```bash
opc run "添加单元测试" --auto-confirm
```

### 查看帮助

```bash
opc --help
opc run --help
```

## 许可证

本项目仅供学习和研究使用，未经授权不得用于商业用途。
