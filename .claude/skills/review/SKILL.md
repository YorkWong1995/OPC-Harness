---
name: review
description: Read pending diff, PRs, task results, or selected files and produce a structured review without modifying code.
---

# review

对 pending diff、PR、任务结果或指定文件做只读评审，识别阻塞问题、非阻塞建议和风险结论；该 skill 只输出评审意见，不直接修改代码或执行修复。

## 用法

`/review <pending diff、PR、任务结果或文件范围>`

## 目标

- 找出会影响正确性、安全性、可维护性或验收结论的阻塞问题
- 区分 blocking 与 non-blocking 建议，避免把风格偏好当作阻塞项
- 用文件路径、行号、命令或 diff 片段支撑每条结论
- 给出 `pass` / `needs-work` / `needs-info` 的明确评审结论

## 适用场景

- 提交前需要检查 pending diff 是否满足任务目标
- PR 或补丁需要独立只读评审
- 任务结果需要核对范围、风险和验证证据
- 指定文件需要检查潜在缺陷或文档漂移

## 不适用场景

- 直接修改代码或文档
- 代替 `/bugfix` 执行修复
- 代替 `/acceptance-check` 给出最终 QA 验收
- 在没有 diff、文件或任务结果的情况下猜测问题

## 执行规则

1. 先确认评审对象和任务目标；缺少目标时只做通用风险评审并标记 `needs-info`。
2. 只读评审，不写入文件、不自动修复、不触发发布或外部副作用。
3. 每条 blocking 问题必须说明影响、证据和建议修正方向。
4. non-blocking 建议不得阻止通过，除非它会破坏验收标准或安全边界。
5. 评审结论必须与问题分类一致：存在 blocking 时为 `needs-work`；信息不足时为 `needs-info`；无 blocking 时可为 `pass`。

## 输出骨架

```
[评审对象] ...
[任务目标/验收标准] ...
[Blocking 问题]
- 问题 / 影响 / 证据 / 建议修正方向
[Non-blocking 建议]
- 建议 / 理由 / 证据
[风险判断]
- 正确性 / 安全 / 兼容性 / 测试 / 发布
[结论] pass / needs-work / needs-info
[后续动作] ...
```

## 验收

- 明确 review 是只读评审，不直接修改代码
- 输入覆盖 pending diff、PR、指定文件和任务结果
- 输出包含 blocking、non-blocking、风险判断和明确结论
- 每条问题或建议都要求引用文件路径、行号、命令或 diff 证据
