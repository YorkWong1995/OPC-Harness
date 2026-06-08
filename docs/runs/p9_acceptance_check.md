# P9 Overall Acceptance Check

## 验收对象

- P9 阶段总体验收：Qt project type/plugin pack、Qt 5.14.2 Widgets + CMake 生成、run artifacts、用户文档、第二 project type 样例插件和插件隔离验证。
- 上游输入：P9-QT-15 QA 验收报告、P9-DOC-03 walkthrough、P9-EXT-02 插件隔离 evidence、`tasks-p9.md` P9 全部任务记录。
- 验收边界：只验收 P9 已定义范围；QML、qmake、Qt Designer `.ui`、Qt6 验收、自动安装依赖、远程构建和默认启用 Qt 插件均不属于本阶段。

## 验收标准

1. Qt 插件可按需启用，默认不加载 Qt project type。
2. 未启用 Qt 插件时，核心 OPC 和 `project-types list` 不检查 Qt 环境、不加载 Qt 模板、不写 artifacts/templates。
3. 启用 Qt 插件后，可生成最小 Qt 5.14.2 Widgets + CMake 项目。
4. Qt 生成结果包含 planned/generated file list，并写入 trace inspect 可见的 run artifact。
5. 环境缺失时，诊断包含缺失项、检查命令、配置路径建议和关闭 Qt 插件方式。
6. CMake/Qt 构建链路有结构 smoke、CMake 项目识别和真实构建执行或 skip 证据。
7. README、文档索引和 walkthrough 说明如何启用、生成、构建、查看 trace 和排错。
8. 插件机制能支持后续 project type 扩展，且样例证明能力不是 Qt 专用。
9. 长任务 evidence / handoff / read_before_start 足以支撑清空上下文后的恢复。

## 检查方法

- 读取任务记录：`tasks-p9.md` 中 P9-QT-15、P9-DOC-03、P9-EXT-02 和 P9-ACCEPT-01 条目。
- 读取验收证据：
  - [p9_qt_acceptance_check.md](p9_qt_acceptance_check.md)
  - [qt-generation.md](qt-generation.md)
  - [test_project_type_plugins.py](../../tests/test_project_type_plugins.py)
  - [test_cli_smoke.py](../../tests/test_cli_smoke.py)
  - [test_qt_generation.py](../../tests/test_qt_generation.py)
- 执行定向总体验收命令：

```bash
python -m pytest tests/test_cli_smoke.py::test_project_types_list_without_plugins_is_read_only tests/test_cli_smoke.py::test_project_types_list_loads_enabled_manifest tests/test_cli_smoke.py::test_project_types_list_reports_qt_environment_diagnostics tests/test_cli_smoke.py::test_generate_qt_requires_enabled_plugin_without_writing tests/test_cli_smoke.py::test_generate_qt_prints_dependency_diagnostics_without_blocking tests/test_cli_smoke.py::test_generate_qt_dry_run_lists_files_without_writing tests/test_cli_smoke.py::test_generate_qt_writes_rendered_files tests/test_qt_generation.py tests/test_project_type_plugins.py tests/test_project_types.py tests/test_workflow_pack_docs.py
```

结果：`22 passed, 1 skipped in 3.36s`。

## 结果记录

| 标准 | 结果 | 证据 |
| --- | --- | --- |
| Qt 插件按需启用 | 通过 | `test_project_types_list_without_plugins_is_read_only` 验证默认 `enabled_plugins=[]`；`test_project_types_list_loads_enabled_manifest` 验证启用后加载 `qt` |
| 未启用时核心轻量 | 通过 | `check_qt_environment.assert_not_called()`、`environment_diagnostics == {}`、目标项目无 `artifacts` / `templates` |
| 启用后生成最小 Qt 项目 | 通过 | `test_generate_qt_writes_rendered_files` 验证 `CMakeLists.txt`、Qt5 5.14 Widgets CMake 内容和模板占位符清理 |
| run artifact 可观测 | 通过 | `test_generate_qt_dry_run_lists_files_without_writing` 验证 `qt_generation.json`、`.opc_state.json artifact_paths` 和 `trace_inspect` 可见 `qt_generation` |
| 缺依赖诊断可读 | 通过 | `test_project_types_list_reports_qt_environment_diagnostics` 和 `test_generate_qt_prints_dependency_diagnostics_without_blocking` 验证缺失项、`Qt5_DIR`、`cmake --version` 和关闭插件建议 |
| CMake/Qt 构建链路证据 | 通过 | `tests/test_qt_generation.py` 覆盖结构 smoke、CMake project detection 和真实 Qt 5.14.2 构建 skip 原因 |
| 用户文档完整 | 通过 | `README.md` Qt quickstart、`docs/DOCS_STRUCTURE.md` / `docs/plan/architecture.md` 文档入口、`docs/runs/qt-generation.md` walkthrough 已完成；`tests/test_workflow_pack_docs.py` 通过 |
| 后续 project type 扩展 | 通过 | `examples/opc_plugins/sample_project_type/` 提供非 Qt `static-site` 样例；`tests/test_project_type_plugins.py` 验证禁用不加载、启用只注册 `static-site` |
| 长任务可恢复性 | 通过 | `tasks-p9.md` 每个完成任务均写入 evidence/handoff；本报告完成后 P9-ACCEPT-01 写回最终 evidence/handoff |

## 是否通过

结论：通过。

未通过项：无。

可恢复性结论：可清空上下文继续。P9 阶段的任务清单、Qt QA 报告、总体验收报告、walkthrough、插件样例、测试名称和关键路径均已记录；若后续继续，应从下一阶段任务或新 `tasks-*.md` 开始。

备注：真实 Qt 5.14.2 构建未在当前机器执行成功，因为本机缺少完整 Qt/CMake/compiler 链路；本阶段按验收标准记录 skip 原因并以结构 smoke、CMake detection、diagnostics 和 artifact 验证作为通过证据。
