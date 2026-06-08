# 文档说明

## 公开文档

- `README.md` - 项目介绍、安装方式、CLI 使用入口
- `CLAUDE.md` - Claude 协作规范入口
- `LICENSE` - 开源许可证

## 内部文档（仅保留本地）

以下文档包含项目内部规划、开发过程记录等，仅保留本地：

### 规划文档 (docs/plan/)
- `vision.md` - 项目愿景与定位
- `architecture.md` - 架构设计
- `organization.md` - 组织结构
- `workflow.md` - 工作流程
- `roadmap.md` - 路线图
- `execution.md` - 执行计划
- `success.md` - 成功标准
- `ai_app_audit_next_steps.md` - AI 应用开发视角拷问总结与后续优先级
- `qt-generation-prd.md` - Qt 5.14.2 Widgets + CMake 生成能力 PRD，说明插件启用边界、模板范围、环境检测和验收要求

### Claude 协作文档 (docs/claude/)
- `roles.md` - 角色职责
- `standards.md` - 文档标准
- `discipline.md` - 执行纪律
- 长任务规则入口：`standards.md` 定义任务字段与恢复字段，`discipline.md` 定义上下文恢复、subagent 边界和换会话清单
- 任务生成 / 自检 / 验收：`.claude/skills/task-spec/SKILL.md`、`.claude/skills/implementation-check/SKILL.md`、`.claude/skills/acceptance-check/SKILL.md`

### 协作资产索引
- `.claude/skills/*/SKILL.md` - 可调用 skill：task-spec、implementation-check、acceptance-check、bugfix、test-spec、review、release-check、token-report 等
- `docs/workflow-packs/README.md` - workflow pack 索引，覆盖 bugfix、review、docs-update、release-check、qt-generation
- `docs/workflow-packs/qt-generation.md` - Qt 生成 workflow pack，说明 Qt 插件启用、生成、环境诊断、构建验证、QA 验收与 trace/artifact 要求
- `scripts/README.md` - 脚本入口索引，说明 run/check/review/cost/upload 分类与风险边界
- `.claude/agents/README.md` - agent 资产索引，说明 PM、Engineer、QA 样板及其与 runtime agent / skill 的区别

### 分享文档 (docs/share/)
- `internal_technical_share.md` - 公司内部技术分享文档，介绍项目能力、技术栈、模块优化与后续计划

### 脚本入口盘点

| 脚本 | 分类 | 当前决策 | 说明 |
| --- | --- | --- | --- |
| `run_opc.py` | run | 保留 | 兼容本地开发入口，转发到 `opc.cli.main()` |
| `run_tasks.py` | run/review | 保留 | 自动任务执行器，涉及 Claude CLI、文件写入和自动提交，使用前需确认任务范围 |
| `pre_upload_check.sh` | check | 保留 | 上传前本地检查入口，适合后续包装到 `scripts/check-*` |
| `upload_to_github.sh` | upload | 暂不自动迁移 | 未跟踪且含 `git add .`、commit、remote、push 等高风险动作，后续如纳入需保留人工确认 |

### 开发记录文档 (docs/)
- `*_summary.md` - 各类总结文档
- `*_issues.md` - 问题记录
- `*_comparison.md` - 对比分析
- `*_roadmap.md` - 改进路线图
- `*_matrix.md` - 优先级矩阵
- `IMPORTANT_*.md` - 重要说明
- `harness_*.md` - Harness 相关文档
- `knowledge-*.md` - 知识库设计

## 为什么这样划分？

**公开文档**：帮助其他开发者理解和使用项目
**内部文档**：记录项目演进过程、设计决策、内部规范，属于项目知识库

这样既保持了开源项目的简洁性，又保留了完整的项目历史和上下文。
