---
name: task-spec
description: Generate or append a task entry into tasks-pX.md following the task-list field standard defined in docs/claude/standards.md.
---

# task-spec

按 [docs/claude/standards.md#任务清单应至少包含](../../../docs/claude/standards.md#任务清单应至少包含) 字段，生成单条任务条目并追加到指定 `tasks-pX.md` 文件。

## 用法

`/task-spec <文件名> <任务描述>`

示例：`/task-spec tasks-p5.md 给 RAG 加中文分词器`

## 字段要求

每条任务必须包含基础字段和长任务可恢复字段：

- `id`：稳定任务编号；无现有编号时按目标任务文件的编号风格生成。
- 任务名称
- 责任角色（CEO / PM / Architect / Engineer / QA / Ops / Growth）
- 输入（文件路径 / 现有结构 / 数据来源）
- 输出（被修改/新增的文件、产物）
- `depends_on`：前置任务 ID；无依赖时写 `none`。
- 完成标准（可验证的判断条件）
- `read_before_start`：开始或继续前必须读取的任务条目、依赖产物、相关文件、pending diff 或验收记录。
- `execution`：执行主体，取值参考 `main`、`explore`、`skill`、`manual_review`、`qa_acceptance`。
- `evidence`：完成时填写产物、验证方式、验证结果或未验证原因；新任务可写 `pending`。
- `handoff`：跨会话时填写当前状态、下一步、阻塞项、需重读文件和最近验证结果；新任务可写 `pending`。

## 输出格式

遵循项目现行任务条目格式，并显式写入长任务字段；不得只依赖 `files/context` 注释承载恢复信息：

```
- [ ] <id> <任务名称> <!-- files: <受影响文件列表> --> <!-- context: <责任角色 / 输入 / 输出 / 完成标准> --> <!-- depends_on: <none|任务ID列表> --> <!-- read_before_start: <必读条目/文件/证据> --> <!-- execution: <main|explore|skill|manual_review|qa_acceptance> --> <!-- evidence: <pending|产物+验证+结果> --> <!-- handoff: <pending|当前状态+下一步+阻塞项+需重读文件+最近验证> --> <!-- auto|review|order|decision -->
```

执行标注：
- `auto` — 可由 Agent 直接小步执行
- `review` — 需要人工取舍/评审
- `order` — 必须在前置任务后顺序执行
- `decision` — 已确认的决策

## 执行规则

1. 读取目标 `tasks-pX.md` 现有结构，保持分组（P0/P1/P2... 或自定义分组）一致。
2. 字段缺失时不得猜测，要求用户补充或显式标记"待补充"。
3. 同一文件内任务编号若已存在，按现有编号风格延续。
4. 写入前展示生成结果，确认后再 Edit/Write。
5. 默认优先细颗粒度拆分：一条任务尽量只覆盖一个文件类型、一个流程步骤或一个可验收目标；如果任务包含多个输出、多个阶段或多个验收点，优先拆成更小任务，除非用户明确要求合并。
6. 若拆分后的任务之间存在先后关系，必须显式标注依赖与顺序，避免把定义、实现、验证和索引混在同一条里。

## 验收

- 生成条目包含全部 6 个字段
- 条目格式与目标文件其他条目一致（同样的 HTML 注释结构）
- 不破坏目标文件已有内容
