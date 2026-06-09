# P10 Acceptance Check

## 验收对象

[tasks-p10.md](../../tasks-p10.md) 中除 `## 4. P1 - 真实环境验证矩阵` 外的 P10 阶段任务：工业化边界、release gate、数据治理、workflow pack runtime 化、安全/插件治理、RAG eval、文档入口与实现自检。第 4 节 `P10-ENV-01/02/03` 按用户要求跳过，不作为本次验收阻塞项。

## 验收标准

- 工业化边界：P10 仍聚焦本地单人 CLI 产品底座，不承诺团队平台、常驻服务、多租户或企业私有化控制面。
- Release gate：覆盖 CI/测试、CLI smoke、Docker 补验、artifact 兼容、RAG eval、安全扫描、文档索引；本地脚本不发布、不 push、不上传、不删除。
- 数据治理：artifacts/index/memory 的保留、清理、敏感信息边界明确；doctor/cleanup 只读或 dry-run。
- Workflow pack runtime：manifest schema 能表达必填字段、权限、stages/transitions，并提供只读发现和低风险 smoke。
- 安全/插件治理：插件 trust policy 明确，project type manifest 路径越界、未知字段、权限越界可拒绝并有测试。
- RAG eval：golden eval 标准、轻量脚本和 release gate 集成完成；输出 top-k、hit/miss、MRR/NDCG 与失败原因。
- 文档入口：README、harness guide、DOCS_STRUCTURE、scripts/new tools/workflow pack README 可定位新增入口。
- 长任务可恢复性：已完成项具备 evidence/handoff；跳过的环境矩阵有 skipped 说明；实现自检建议进入 QA。

## 检查方法

- 读取任务与 evidence：[tasks-p10.md:9](../../tasks-p10.md#L9)、[tasks-p10.md:53](../../tasks-p10.md#L53)、[tasks-p10.md:30-32](../../tasks-p10.md#L30-L32)。
- 读取实现自检：[p10_implementation_check.md:13](p10_implementation_check.md#L13)、[p10_implementation_check.md:51-53](p10_implementation_check.md#L51-L53)、[p10_implementation_check.md:82](p10_implementation_check.md#L82)。
- 读取 release/RAG 报告：[release_report.local.json:57-59](release_report.local.json#L57-L59)、[rag_eval.local.json:4-10](rag_eval.local.json#L4-L10)。
- 读取边界/文档：[roadmap.md:200-244](../plan/roadmap.md#L200-L244)、[README.md:169-194](../../README.md#L169-L194)。
- 读取代码与测试证据：[cli.py:169-196](../../src/opc/cli.py#L169-L196)、[cli.py:884-980](../../src/opc/cli.py#L884-L980)、[workflow_spec.py:138-253](../../src/opc/workflow_spec.py#L138-L253)、[project_types.py:104](../../src/opc/project_types.py#L104)、[project_types.py:158-166](../../src/opc/project_types.py#L158-L166)、[rag_eval.py:49-95](../../src/opc/knowledge/rag_eval.py#L49-L95)。
- 复核测试覆盖：[test_cli_smoke.py:219-236](../../tests/test_cli_smoke.py#L219-L236)、[test_plugin_security.py:97-115](../../tests/test_plugin_security.py#L97-L115)。
- 复核定向验证命令：`python -m pytest tests/test_cli_smoke.py tests/test_workflow_spec_integration.py tests/test_plugin_security.py tests/test_project_type_plugins.py tests/test_knowledge_index_paths.py tests/test_project_kb_quality.py -q`，结果 `85 passed`。

## 结果记录

- 工业化边界 → 通过。证据：[roadmap.md:200-202](../plan/roadmap.md#L200-L202) 明确 P10 只收敛本地单人 CLI 产品底座；实现自检确认未引入团队平台等超范围能力 [p10_implementation_check.md:13](p10_implementation_check.md#L13)。
- Release gate → 通过。证据：[roadmap.md:206-219](../plan/roadmap.md#L206-L219)、[release_report.local.json:57-59](release_report.local.json#L57-L59) 显示 blocking_items=[]、recommendation=ready。
- 数据治理 → 通过。证据：[README.md:190-194](../../README.md#L190-L194)、[roadmap.md:221-226](../plan/roadmap.md#L221-L226) 明确 artifacts/index/memory 保留、清理和只读/dry-run 边界；CLI 支持 doctor/cleanup [cli.py:187-196](../../src/opc/cli.py#L187-L196)、[cli.py:942-980](../../src/opc/cli.py#L942-L980)。
- Workflow pack runtime → 通过。证据：[workflow_spec.py:138-253](../../src/opc/workflow_spec.py#L138-L253) 定义 manifest schema/discovery；CLI 支持 `workflow-packs list/smoke` [cli.py:169-184](../../src/opc/cli.py#L169-L184)、[cli.py:884-939](../../src/opc/cli.py#L884-L939)；测试覆盖 [test_cli_smoke.py:236](../../tests/test_cli_smoke.py#L236)。
- 安全/插件治理 → 通过。证据：[roadmap.md:238-240](../plan/roadmap.md#L238-L240) 定义 trust policy；代码拒绝非法权限和路径越界 [project_types.py:104](../../src/opc/project_types.py#L104)、[project_types.py:158](../../src/opc/project_types.py#L158)，拒绝未知字段 [project_types.py:166](../../src/opc/project_types.py#L166)；测试覆盖 [test_plugin_security.py:97-115](../../tests/test_plugin_security.py#L97-L115)。
- RAG eval → 通过。证据：[roadmap.md:242-244](../plan/roadmap.md#L242-L244)、[rag_eval.py:49-95](../../src/opc/knowledge/rag_eval.py#L49-L95)；报告显示 queries=24、hit_rate=0.7083、MRR=0.5069、NDCG=0.7437 [rag_eval.local.json:4-10](rag_eval.local.json#L4-L10)。
- 文档入口 → 通过。证据：[README.md:169-187](../../README.md#L169-L187) 暴露 diagnostics/release/RAG 命令；[README.md:190-194](../../README.md#L190-L194) 暴露数据治理；[tasks-p10.md:48-49](../../tasks-p10.md#L48-L49) 已记录 DOC evidence。
- 长任务可恢复性 → 通过。证据：任务 evidence/handoff 已回填 [tasks-p10.md:9-26](../../tasks-p10.md#L9-L26)、[tasks-p10.md:36-49](../../tasks-p10.md#L36-L49)；实现自检判断可恢复 [p10_implementation_check.md:55-64](p10_implementation_check.md#L55-L64)。
- 环境矩阵 → 未覆盖但不阻塞。证据：用户明确要求跳过；任务文件中 `P10-ENV-01/02/03` 保留 pending 并标记 skipped [tasks-p10.md:30-32](../../tasks-p10.md#L30-L32)；实现自检列为已知限制 [p10_implementation_check.md:66-72](p10_implementation_check.md#L66-L72)。

## 是否通过

通过。

未通过项：无。

后续补验项：第 4 节真实环境验证矩阵（Docker build/smoke、真实 Qt 5.14.2 构建、跨平台/Python 版本、有/无 API key、有/无 bge/faiss）按用户要求跳过，后续如需要发布到真实环境，应单独恢复 `P10-ENV-01/02/03`。
