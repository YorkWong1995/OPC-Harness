# P3: 产品化与扩展能力

> 来源：tasks.md P3 部分
> 注意：此阶段包含较多需要人工决策的项，标记为 <!-- decision: ... -->，执行时自动跳过

## 13. Web UI / TUI

- [ ] 选型：Streamlit / Gradio / Textual <!-- decision: 需要确定 UI 框架选型，影响后续所有 UI 开发 -->
- [ ] 实现工作流执行页：展示阶段进度、产物内容、审批节点 <!-- decision: 依赖框架选型结果 -->
- [ ] 实现 RAG 查询页：展示检索结果和命中来源 <!-- decision: 依赖框架选型结果 -->
- [ ] 实现历史记录页：展示所有运行记录 <!-- decision: 依赖框架选型结果 -->

## 14. 多 Agent 异步编排

- [ ] 在 Agent 类中实现 observe-think-act 循环框架 <!-- files: src/opc/agent.py --> <!-- context: Agent 持续监听消息、思考、执行，直到任务完成或收到停止信号 -->
- [ ] 在 Environment 中添加异步消息分发支持 <!-- files: src/opc/environment.py --> <!-- context: 支持消息并行投递，多个 Agent 可同时接收和处理消息 -->
- [ ] 实现角色并行执行：Architect 和 Growth 可同时产出 <!-- files: src/opc/workflow.py --> <!-- context: 在工作流中标记可并行的阶段，使用 asyncio 或线程池并行执行 -->

## 15. Action/Tool 注册机制

- [ ] 在 src/opc/ 下新建 tools/ 目录，创建 tool_registry.py <!-- files: src/opc/tools/ -->
- [ ] 实现 @register_tool 装饰器：自动注册工具名、描述、参数 schema <!-- files: src/opc/tools/tool_registry.py -->
- [ ] 重构 agent.py 的工具分发逻辑：从硬编码 dispatch 改为查询 tool_registry <!-- files: src/opc/agent.py -->
- [ ] 实现动态加载：从 opc_plugins/ 目录扫描并加载外部工具 <!-- files: src/opc/tools/tool_registry.py --> <!-- context: 使用 importlib 动态导入 opc_plugins/ 下的 Python 模块 -->

## 16. 运行观测

- [ ] 在 Agent.run() 中添加 token 计数：从 API response.usage 提取 input/output tokens <!-- files: src/opc/agent.py -->
- [ ] 在 HarnessWorkflow 中添加各阶段耗时统计 <!-- files: src/opc/workflow.py --> <!-- context: 使用 time.monotonic() 记录每个阶段的开始和结束时间 -->
- [ ] 实现 generate_metrics()：生成 artifacts/run_metrics.json <!-- files: src/opc/workflow.py --> <!-- context: 包含 token 消耗、耗时、工具调用次数 -->
- [ ] 编写 tests/test_metrics.py：测试 token 计数和耗时统计 <!-- files: src/opc/workflow.py, src/opc/agent.py -->
