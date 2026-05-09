# P0: 稳定性与可交付闭环

## 1. 测试体系正规化

- [x] 创建 tests/ 目录并添加 __init__.py <!-- context: mkdir tests && touch tests/__init__.py -->
- [x] 迁移 test_environment.py 到 tests/test_environment.py，改为 pytest 风格（去掉 if __name__ 块，函数名保持 test_ 前缀） <!-- files: test_environment.py -->
- [x] 迁移 test_message.py 到 tests/test_message.py，改为 pytest 风格 <!-- files: test_message.py -->
- [x] 迁移 test_memory.py 到 tests/test_memory.py，改为 pytest 风格 <!-- files: test_memory.py -->
- [x] 迁移 test_new_tools.py 到 tests/test_tools.py，改为 pytest 风格 <!-- files: test_new_tools.py -->
- [ ] 在 pyproject.toml 中添加 [tool.pytest.ini_options] 配置：testpaths = ["tests"]，addopts = "-v" <!-- files: pyproject.toml -->
- [ ] 编写 tests/test_workflow.py：测试 HarnessWorkflow 初始化和阶段流转（mock API 调用） <!-- files: src/opc/workflow.py -->
- [ ] 编写 tests/test_agent.py：测试 Agent 工具分发逻辑和消息缓冲区 <!-- files: src/opc/agent.py -->
- [ ] 编写 tests/test_knowledge.py：测试 BM25 索引构建和查询、chunker 分块逻辑 <!-- files: src/opc/knowledge/bm25_index.py, src/opc/knowledge/chunker.py -->
- [ ] 运行 python -m pytest 确认所有测试通过，修复发现的问题 <!-- context: 这是验收任务，确保整个测试套件可以一键跑通 -->

## 2. 文档与代码一致性修复

- [ ] 更新 README.md 的目录结构描述，使其与当前实际结构一致 <!-- files: README.md -->
- [ ] 在 README.md 中补充 opc index 和 opc query 的 CLI 使用示例 <!-- files: README.md -->
- [ ] 在 README.md 中更新依赖安装说明：pip install -e . 和 pip install -e .[bge] <!-- files: README.md -->
- [ ] 删除 docs/improvement_roadmap.md（内容已过时，核心改进已在代码中实现） <!-- files: docs/improvement_roadmap.md -->
- [ ] 删除 docs/priority_matrix.md（与当前项目状态不符） <!-- files: docs/priority_matrix.md -->

## 3. CLI 端到端冒烟测试

- [ ] 编写 tests/test_cli_smoke.py：测试 opc index --name test-idx --dirs test_data 能成功构建索引 <!-- files: src/opc/cli.py -->
- [ ] 在 tests/test_cli_smoke.py 中添加：测试 opc query "测试问题" --name test-idx --no-llm 能返回结果 <!-- files: src/opc/cli.py -->
- [ ] 在 tests/test_cli_smoke.py 中添加：测试 opc run 的参数解析（不实际调用 API，mock anthropic client） <!-- files: src/opc/cli.py, src/opc/workflow.py -->

## 4. 敏感与生成文件治理

- [ ] 删除 .env 文件（.env.example 已存在，保留即可） <!-- files: .env -->
- [ ] 清理所有 __pycache__ 目录 <!-- context: find . -type d -name __pycache__ -exec rm -rf {} + -->
- [ ] 清理 workspace/*/index/ 下的生成索引文件 <!-- context: rm -rf workspace/*/index/ -->
- [ ] 在 .gitignore 中添加 workspace/*/index/ 和 workspace/*/artifacts/ 和 *.log <!-- files: .gitignore -->
- [ ] 运行 git status 确认无敏感文件和生成产物被跟踪 <!-- context: 验收任务 -->
