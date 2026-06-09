# Scripts

`scripts/` 保存项目级脚本入口的说明和轻量 wrapper。根目录历史入口暂时保留，避免破坏已有使用方式；新增或迁移脚本优先放在本目录，并在 README 与 DOCS_STRUCTURE 中建立索引。

## 分类

| 分类 | 命名建议 | 说明 | 风险边界 |
| --- | --- | --- | --- |
| run | `run-*.py` / `run-*.sh` | 启动 OPC CLI、workflow 或任务执行器 | 可能调用模型、写文件或触发 workflow |
| check | `check-*.sh` / `check-*.py` | 本地只读检查、结构检查、上传前检查 | 默认不提交、不推送、不修改远端 |
| review | `review-*.py` / `review-*.sh` | 只读审查、diff 检查、任务结果检查 | 不直接修复代码，不自动提交 |
| cost | `cost-*.py` / `cost-*.sh` | 读取 run metrics，输出 token/cost/duration 报告 | 只读 artifacts，不调用模型 |
| upload | `upload-*.sh` | 上传、发布、远端同步等入口 | 必须交互确认，禁止静默 `git add .`、commit、push |

## 入口规则

- 保留根目录已有入口作为兼容层；迁移时优先新增 wrapper，不直接删除旧脚本。
- wrapper 必须说明真实调用对象、是否只读、是否写文件、是否触发 git 操作。
- 上传、发布、push、remote 修改、删除文件等高风险动作必须保留人工确认。
- 自动任务执行器默认按危险入口处理，使用前需要确认任务范围、提交策略和验证方式。
- 脚本新增后同步更新 README、DOCS_STRUCTURE 或本目录索引。

## 当前入口

| scripts 入口 | 调用对象 | 分类 | 说明 |
| --- | --- | --- | --- |
| `run-opc.py` | `../run_opc.py` | run | 兼容启动 OPC CLI，不移动根入口 |
| `run-tasks.py` | `../run_tasks.py` | run/review | 兼容启动自动任务执行器，使用前确认任务范围和提交策略 |
| `check-pre-upload.sh` | `../pre_upload_check.sh` | check | 上传前检查 wrapper，只做本地检查 |
| `check-release.py` | local release gate | check | 生成本地 release report；不发布、不 push、不上传、不删除 |
| `run-rag-eval.py` | `opc.knowledge.rag_eval` | check | 轻量 RAG golden eval，不调用 LLM，不重建大型索引 |
| `cleanup-dry-run.py` | artifacts/index scanner | check | 只列出清理候选、原因和风险，不删除文件 |
| `upload-to-github.sh` | `../upload_to_github.sh` | upload | 高风险上传 wrapper，执行前必须输入 `upload` 确认 |

## 当前策略

| 根入口 | scripts 策略 |
| --- | --- |
| `run_opc.py` | 已提供 `scripts/run-opc.py` wrapper，根入口保留 |
| `run_tasks.py` | 已提供 `scripts/run-tasks.py` wrapper，根入口保留 |
| `pre_upload_check.sh` | 已提供 `scripts/check-pre-upload.sh` wrapper，根入口保留 |
| `upload_to_github.sh` | 已提供 guarded `scripts/upload-to-github.sh` wrapper；根入口本身仍不自动提交，直接使用需人工确认风险 |
