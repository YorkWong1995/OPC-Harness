# P2: 提升 RAG / Knowledge 能力

> 来源：tasks.md P2 部分

## 9. 检索效果评估集

- [x] 创建 tests/fixtures/rag_eval_dataset.json：包含 10-20 个问答对，覆盖代码、文档、配置三类内容 <!-- context: 格式为 [{"question": "...", "relevant_files": ["..."], "relevant_chunks": ["..."]}] -->
- [x] 编写 tests/test_rag_quality.py：测试 top-k 命中率和 MRR 指标 <!-- files: src/opc/rag.py, src/opc/rag_bm25.py --> <!-- context: 基于评估集计算检索质量，阈值暂定 top-3 命中率 > 60% -->

## 10. 索引增量更新

- [x] 在 indexer 中添加文件变更检测逻辑：基于 mtime 或 hash 判断哪些文件需要重新索引 <!-- files: src/opc/knowledge/ -->
- [x] 实现增量索引构建：只重新处理变更的文件，保留未变更文件的索引 <!-- files: src/opc/knowledge/ -->
- [x] 在 CLI 添加 opc index --incremental 选项 <!-- files: src/opc/cli.py -->
- [x] 编写 tests/test_incremental_index.py：测试增量更新的正确性 <!-- files: src/opc/knowledge/ -->

## 11. RAG 工具化接入 Agent

- [x] 在 Agent 的工具列表中添加 search_knowledge 工具定义 <!-- files: src/opc/agent.py --> <!-- context: 工具定义包含 query (string) 和 top_k (int) 参数 -->
- [x] 在 agent.py 中实现 search_knowledge 工具的分发逻辑：调用 RAG 检索并返回结果 <!-- files: src/opc/agent.py, src/opc/rag.py -->
- [x] 在 roles.py 的 Engineer 角色 prompt 中添加引导：如果不确定实现细节，使用 search_knowledge 工具查询 <!-- files: src/opc/roles.py -->
- [x] 在 roles.py 的 QA 角色 prompt 中添加引导：使用 search_knowledge 工具验证实现是否符合项目文档 <!-- files: src/opc/roles.py -->

## 12. 代码分块增强

- [x] 在 chunker.py 添加 Markdown 按标题层级分块策略 <!-- files: src/opc/knowledge/chunker.py --> <!-- context: 按二级标题 ## 分块，保留标题作为上下文前缀 -->
- [x] 在 chunker.py 添加 Python 按函数/类分块策略（基于正则匹配） <!-- files: src/opc/knowledge/chunker.py --> <!-- context: 匹配 def 和 class 定义，将每个函数/类作为独立 chunk -->
- [x] 在 chunker.py 添加 JSON/YAML 按顶层 key 分块策略 <!-- files: src/opc/knowledge/chunker.py -->
- [x] 在 chunker.py 添加自动格式检测：根据文件扩展名选择分块策略 <!-- files: src/opc/knowledge/chunker.py -->
