# Workflow Packs

Workflow pack 是项目级可复用工作流说明单元，用来固定一类任务的输入、角色边界、权限、产物、验收标准和 trace 记录要求。

## 适用范围

- 适合沉淀重复出现的任务类型，例如 bugfix、review、docs-update、release-check。
- P10 起提供 `opc workflow-packs list` 只读发现入口，用于列出 pack manifest、kind、权限、runtime 可执行性和禁用原因。
- `opc workflow-packs smoke --id docs-update` 只执行低风险 runtime smoke，生成 run_id、trace 和 `workflow_pack_smoke.json`，不触发模型或真实发布。
- 若 pack 声明为 `claude_skill`，默认由 `.claude/skills/` 中的协作 skill 执行。
- 若 pack 声明为 `opc_runtime_workflow`，默认由 `opc run` / `opc resume` 产出 run artifacts、trace 和 QA 记录。

## 文件命名

- `README.md`：目录说明、维护规则和 pack 索引。
- `manifest-template.md`：可复制的 manifest 字段模板。
- `<pack-id>.md`：单个 workflow pack 说明，文件名使用稳定小写 kebab-case，例如 `bugfix.md`。

## Pack 字段

每个 pack 至少包含以下字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 稳定标识，例如 `bugfix`、`review`、`docs-update` |
| `kind` | `claude_skill` 或 `opc_runtime_workflow` |
| `owner_roles` | 主要责任角色 |
| `inputs` | 任务描述、目标文件、约束、验收标准等输入 |
| `outputs` | 代码变更、评审记录、文档更新、验收记录等输出 |
| `permissions` | 只读、写入、命令执行或需要审批的能力 |
| `acceptance` | 可检查的完成标准 |
| `trace` | 需要落入 run trace 的关键事件或 artifact |

## 维护规则

1. 未声明写入或命令执行权限时，默认只读。
2. Pack 不应复制完整 skill 内容，只引用对应 skill 或 runtime workflow 边界。
3. 涉及发布、上传、删除、迁移、push 或共享基础设施的 pack 必须声明人工确认节点。
4. 修改 pack 时同步检查 `docs/plan/workflow.md` 的 Workflow Pack 规范是否仍一致。
5. 新增 pack 后需要更新本 README 的索引。

## 当前 Pack 索引

| Pack | kind | 状态 | 说明 |
| --- | --- | --- | --- |
| `bugfix` | `opc_runtime_workflow` | runtime 候选 | 缺陷定位、最小修复、定向验证和 QA 验收 |
| `review` | `claude_skill` | skill | PR、pending diff 或任务结果的只读评审 |
| `docs-update` | `opc_runtime_workflow` | runtime smoke | 文档漂移修复、规范补充和索引检查；P10 用作低风险 smoke |
| `qt-generation` | `opc_runtime_workflow` | 可选插件 runtime | Qt Widgets + CMake 生成、环境诊断、构建验证和 QA 验收 |
| `release-check` | `claude_skill` | skill + script | 发布前只读检查、风险判断、release report 和回滚条件确认 |
