---
name: token-report
description: Read OPC run artifacts and summarize token, API call, duration, and cost-related usage without invoking models or tools.
---

# token-report

只读分析 OPC run artifacts，基于 `run_metrics.json`、`run_trace.json` 和 `run_events.jsonl` 汇总 token、API 调用、耗时和成本相关字段；不得重新调用模型、工具或触发新的 workflow。

## 用法

`/token-report <latest run 或 artifacts 路径>`

## 目标

- 汇总单次 run 的 input/output tokens、api_calls 和 duration
- 展示分阶段消耗和最高消耗阶段
- 标记异常项、缺失字段或旧 metrics 兼容情况
- 给出不改变代码的成本/上下文优化建议

## 适用场景

- 需要解释一次 workflow run 的 token 和调用消耗
- 需要对比阶段消耗，定位高成本阶段
- 需要检查 run artifacts 是否包含足够的 metrics 字段
- 需要为后续 cost trend 或优化任务提供只读证据

## 不适用场景

- 重新执行 workflow 或模型调用
- 修改 artifacts、代码或配置
- 代替真实账单或供应商计费记录
- 对缺失 metrics 做无依据估算

## 输出字段模板

字段应优先直接对应 `run_metrics.json` 的现有或计划字段；字段缺失时标注为“缺失”：

| 字段 | 来源 | 输出要求 |
| --- | --- | --- |
| `run_id` | `run_trace.json` 或 artifacts 路径 | 标识本次 run |
| `input_tokens` | `run_metrics.json.totals.input_tokens` | 输出总输入 token |
| `output_tokens` | `run_metrics.json.totals.output_tokens` | 输出总输出 token |
| `api_calls` | `run_metrics.json.totals.api_calls` | 输出 API 调用总数 |
| `duration_seconds` | `run_metrics.json.totals.duration_seconds` | 输出总耗时 |
| `stage_usage` | `run_metrics.json.stages` | 按 stage 列出 tokens、api_calls、duration、model、estimated_cost |
| `highest_usage_stage` | `stage_usage` 派生 | 标出 token 或 cost 最高阶段 |
| `estimated_cost` | `run_metrics.json.totals.estimated_cost` | 仅在 artifacts 已存在时输出 |
| `currency` | `run_metrics.json.totals.currency` | 缺失时标注不适用 |
| `pricing_source` | `run_metrics.json.totals.pricing_source` | 说明价格来源或缺失 |
| `anomalies` | metrics/trace/events 对比 | 标记缺字段、异常耗时、异常调用数 |
| `optimization_suggestions` | 分阶段消耗派生 | 给出证据驱动的优化建议 |

## 执行规则

1. 只读取用户指定或 latest run 的 artifacts。
2. 不调用模型、不执行 workflow、不修改 run 文件。
3. 缺失字段必须标记为“缺失”或“不适用”，不得猜测。
4. 成本字段只能按 artifacts 中已有或配置中声明的估算字段说明。
5. 优化建议必须对应可观察消耗，不提出无证据的大范围重构。

## 示例

- `/token-report latest run`
- `/token-report artifacts/runs/20260526-120000/run_metrics.json`

## 报告骨架

```
[分析对象] latest / 指定 artifacts 路径
[读取 artifacts]
- run_metrics.json：存在 / 缺失
- run_trace.json：存在 / 缺失
- run_events.jsonl：存在 / 缺失
[总量]
- input_tokens：...
- output_tokens：...
- api_calls：...
- duration_seconds：...
- estimated_cost：...
- currency：...
- pricing_source：...
[分阶段消耗]
- stage：model / input_tokens / output_tokens / api_calls / duration_seconds / estimated_cost
[最高消耗阶段]
- token 最高：...
- cost 最高：...
[异常项]
- ...
[优化建议]
- ...
[结论] ...
```

## 验收标准

- 示例覆盖 latest run 和指定 artifacts 路径两种用法
- 报告骨架包含读取 artifacts 状态、总量、分阶段消耗、最高消耗阶段、异常项和优化建议
- 缺失 metrics 字段必须标注为缺失或不适用
- 不触发模型、工具、workflow 或 artifacts 写入

## 输出骨架

```
[分析对象] ...
[读取 artifacts] run_metrics.json / run_trace.json / run_events.jsonl
[总量] input_tokens / output_tokens / api_calls / duration / estimated_cost / currency / pricing_source
[分阶段消耗]
- stage: model / input_tokens / output_tokens / api_calls / duration / estimated_cost
[最高消耗阶段] stage / 指标 / 数值
[异常项] ...
[优化建议] ...
[结论] ...
```

## 验收

- 明确只读 artifacts，不重新调用模型或工具
- 覆盖 run_metrics.json、run_trace.json、run_events.jsonl 三类输入
- 输出包含总量、分阶段消耗、异常项和优化建议
- 对缺失字段或旧 metrics 有兼容说明
