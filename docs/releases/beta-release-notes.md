# Beta Release Notes

## 状态

Beta 阶段为条件完成：本地轻量验证已覆盖核心任务，Docker 镜像构建、镜像运行和完整覆盖率门禁由目标环境或 CI 持续验证。

## 新增能力

- 中断恢复与 WorkflowSpec 驱动的状态流转已接入工作流主链路。
- 工具安全审计覆盖路径边界、危险命令拦截、工具调用 trace 与高噪声输出裁剪。
- 成本观测支持 token/API 调用统计、软提示与 hard limit 中断。
- QA rework 改为显式循环，并记录 failure root cause、rollback stage 与验证证据。
- RunStore 使用追加式事件日志，artifact 存储保留版本清单。
- BM25 索引改用 JSON 持久化，避免 pickle 加载风险。
- Dockerfile、Docker 发布 workflow、CI workflow 与可跳过 Docker smoke test 已补齐。

## 验证记录

- `python -m pytest tests/test_docker_smoke.py`：3 passed, 1 skipped（未设置 `OPC_DOCKER_SMOKE_IMAGE` 时跳过真实容器运行）。
- `python -m pytest tests/test_qt_generation.py::test_qt_generation_real_build_when_environment_is_available -q`：作为 Qt 5.14.2 真实构建补验入口；有 Qt/CMake/compiler 时执行 configure/build，无环境时输出 skip 原因并记录到 `docs/runs/p10_qt_real_build_validation.md`。
- P0/P1/P2/P3 任务已按清单完成定向测试与小步提交。
- CI 中配置 `python -m pytest --cov=opc --cov-report=term-missing --cov-fail-under=80` 作为覆盖率门禁。

## 破坏性变更

- `opc --version` 现在作为顶层 CLI 参数提供。
- QA 输出 schema 新增诊断字段：`failure_root_cause`、`rollback_stage`、`diagnostic_summary`。
- 工具结果进入模型上下文前会被裁剪为摘要，完整输出不再无界传回模型。

## 升级说明

- 本地开发继续使用 `pip install -e .`；需要向量嵌入时使用 `pip install -e .[bge]`。
- Docker 镜像 smoke test 需要先提供可运行镜像，并设置 `OPC_DOCKER_SMOKE_IMAGE`。
- 若依赖完整知识检索测试，CI 环境需安装 `[faiss,bge]` 可选依赖。

## 已知限制

- Web UI 仍在 Roadmap 中。
- Docker 构建未在本地执行，需在具备 Docker 的目标环境或 GitHub Actions 中确认。
- 完整覆盖率结果以 CI 为准，本轮未在本机运行全量测试或覆盖率。
