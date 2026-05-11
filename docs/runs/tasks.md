# OPC 项目任务清单

> 最后更新：2026-05-11  
> 原则：先稳定核心能力，再扩展 Agent 协作

---

## P0：稳定性与可交付闭环（1-2 周）

### 1. 测试体系正规化
- [ ] 创建 `tests/` 目录，迁移现有测试脚本
  - 迁移 `test_environment.py` → `tests/test_environment.py`
  - 迁移 `test_message.py` → `tests/test_message.py`
  - 迁移 `test_memory.py` → `tests/test_memory.py`
- [ ] 添加 `pytest.ini` 或 `pyproject.toml` 的 pytest 配置
- [ ] 补充测试用例
  - `tests/test_workflow.py`：最小工作流端到端测试
  - `tests/test_agent.py`：工具调用、RAG 集成测试
  - `tests/test_knowledge.py`：BM25、向量检索、RRF 融合测试
- [ ] 验收标准：`python -m pytest` 一键跑通所有测试

### 2. 文档与代码一致性修复
- [ ] 更新 `README.md`
  - 修正目录结构描述（当前写的是旧路径）
  - 补充 `opc index`/`opc query` CLI 使用示例
  - 更新依赖安装说明（`pip install -e .` 或 `pip install -e .[bge]`）
- [ ] 清理过时路线图
  - 删除或归档 `docs/improvement_roadmap.md`（部分 P0 已实现）
  - 删除或归档 `docs/priority_matrix.md`（与当前状态不符）
- [ ] 验收标准：新用户按 README 能成功运行 `opc run` 和 `opc index`

### 3. CLI 端到端冒烟测试
- [ ] 编写 `tests/test_cli_smoke.py`
  - 测试 `opc run "简单任务" --project test-smoke --auto-confirm`
  - 测试 `opc index --name test-idx --dirs test_data`
  - 测试 `opc query "测试问题" --name test-idx --no-llm`
- [ ] 验收标准：冒烟测试通过，生成 artifacts、索引、查询结果

### 4. 敏感与生成文件治理
- [ ] 清理仓库中的敏感文件
  - 删除 `.env`（保留 `.env.example`）
  - 清理所有 `__pycache__` 目录
  - 清理 `workspace/*/index/` 生成的索引文件
- [ ] 强化 `.gitignore`
  - 添加 `workspace/*/index/`
  - 添加 `workspace/*/artifacts/`
  - 添加 `*.log`
- [ ] 验收标准：`git status` 干净，无敏感文件和生成产物

---

## P1：强化核心 Harness 工作流（2-4 周）

### 5. 工作流断点续跑
- [ ] 设计状态持久化格式（JSON 或 TOML）
  - 记录当前阶段、已完成阶段、产物路径
- [ ] 在 `workflow.py` 添加 `--resume-from <stage>` 支持
  - 支持从 `pm`/`architect`/`engineer`/`qa` 任一阶段恢复
- [ ] 添加状态保存逻辑
  - 每个阶段完成后保存 `artifacts/.opc_state.json`
- [ ] 验收标准：工作流中断后可从上次位置继续

### 6. 角色执行状态持久化
- [ ] 扩展 `artifacts/.opc_state.json` 格式
  - 记录每个阶段的输入、输出、耗时、token 消耗
- [ ] 在 `workflow.py` 添加执行日志记录
- [ ] 生成 `artifacts/run_report.md` 或 JSON
  - 包含任务描述、各阶段耗时、产物路径、审批决策
- [ ] 验收标准：每次运行后可复盘完整执行过程

### 7. Human Review 体验升级
- [ ] 重构 `workflow.py` 的 `review()` 方法
  - 支持 `y`（继续）、`n`（终止）、`r`（退回重做）、`e`（编辑提示）
- [ ] 添加退回重做逻辑
  - 允许修改上一阶段的输入并重新执行
- [ ] 添加跳过阶段选项
  - 允许跳过当前阶段（如 Architect）直接进入下一阶段
- [ ] 验收标准：审批节点支持更灵活的人工干预

### 8. Embedded 开发模板产品化
- [ ] 基于 `docs/opc_embedded_dev_issues.md` 总结经验
- [ ] 在 `roles.py` 添加 `create_embedded_engineer_agent()`
  - 专门的 system prompt，包含嵌入式开发知识
  - 工具白名单包含 C/C++ 编译工具
- [ ] 支持 `opc.toml` 配置 `profile = "embedded"`
  - 自动启用 Embedded Engineer
  - 自动跳过 Architect（简化流程）
- [ ] 验收标准：嵌入式任务使用 `--profile embedded` 生成高质量代码

---

## P2：提升 RAG / Knowledge 能力（4-6 周）

### 9. 检索效果评估集
- [x] 创建 `tests/fixtures/rag_eval_dataset.json`
  - 包含 10-20 个问答对，覆盖代码、文档、配置
- [x] 编写 `tests/test_rag_quality.py`
  - 测试 top-k 命中率、MRR、NDCG
- [x] 验收标准：检索效果量化可追踪

### 10. 索引增量更新
- [x] 在 `indexer.py` 添加增量更新逻辑
  - 检测文件变更（基于 mtime 或 hash）
  - 只重新索引变更的文件
- [x] 添加 `opc index --name <name> --incremental` 命令
- [x] 验收标准：大项目索引更新时间从分钟级降到秒级

### 11. RAG 工具化接入 Agent
- [x] 在 `agent.py` 添加 `search_knowledge` 工具
  - 允许 Agent 主动查询项目知识库
- [x] 在 `roles.py` 的 Engineer/QA prompt 中引导使用
  - "如果不确定实现细节，使用 search_knowledge 工具查询"
- [x] 验收标准：Agent 能主动检索并引用项目文档

### 12. 代码分块增强
- [x] 在 `chunker.py` 添加语义分块策略
  - Markdown：按标题层级分块
  - Python/C++：按函数/类分块（使用 tree-sitter 或正则）
  - JSON/YAML：按顶层 key 分块
- [x] 验收标准：代码库问答的召回率提升 20%+

---

## P3：产品化与扩展能力（6-12 周）

### 13. Web UI / TUI
- [ ] 选型：Streamlit / Gradio / Textual
- [ ] 实现核心页面
  - 工作流执行页：展示阶段、产物、审批节点
  - RAG 查询页：展示检索结果、命中来源
  - 历史记录页：展示所有运行记录
- [ ] 验收标准：可通过 UI 完成完整工作流

### 14. 多 Agent 异步编排
- [ ] 实现 Agent 的 `observe-think-act` 循环
  - 参考 `docs/improvement_roadmap.md` 的设计
- [ ] 支持角色并行执行
  - 如 Architect 和 Growth 可并行产出
- [ ] 验收标准：多角色协作任务耗时减少 30%+

### 15. Action/Tool 注册机制
- [ ] 重构 `agent.py` 的工具分发逻辑
  - 从硬编码 dispatch 改为注册表
- [ ] 添加 `@register_tool` 装饰器
- [ ] 支持动态加载外部工具
  - 从 `opc_plugins/` 目录加载
- [ ] 验收标准：可通过插件扩展工具，无需修改核心代码

### 16. 运行观测
- [ ] 在 `agent.py` 添加 token 计数
  - 记录每次 API 调用的 input/output tokens
- [ ] 在 `workflow.py` 添加耗时统计
  - 记录每个阶段的开始/结束时间
- [ ] 生成 `artifacts/run_metrics.json`
  - 包含 token 消耗、耗时、工具调用次数、失败原因
- [ ] 验收标准：每次运行后可查看详细指标

---

## 快速推进建议

**第一步（本周）**：P0.1 + P0.2  
- 测试体系正规化 + 文档同步
- 成本低、收益高，为后续改功能提供安全网

**第二步（下周）**：P0.3 + P0.4  
- CLI 冒烟测试 + 文件治理
- 确保可交付状态

**第三步（2-3 周）**：P1.5 + P1.7  
- 断点续跑 + Human Review 升级
- 显著提升实际使用体验

**第四步（4-6 周）**：P2.11 + P2.12  
- RAG 工具化 + 代码分块增强
- 提升 Agent 自主能力

---

## 备注

- 所有任务完成后，在对应 `[ ]` 中打勾 `[x]`
- 每个任务完成后，更新"最后更新"日期
- 如有新任务或优先级调整，及时更新本文件
