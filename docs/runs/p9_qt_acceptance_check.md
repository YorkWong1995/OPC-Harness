# P9 Qt Generation QA Acceptance Check

## 验收对象

- P9-QT-15：Qt 生成 QA 验收。
- 验收范围：Qt 插件禁用边界、启用后缺依赖诊断、启用后最小 Qt Widgets + CMake 项目生成、dry-run/artifact 可观测性、Qt 结构 smoke 和真实构建 skip 证据。
- 上游输入：[P9-QT-14 implementation-check](p9_qt_implementation_check.md)、[tasks-p9.md:41-44](../../tasks-p9.md#L41-L44)、[test_qt_generation.py](../../tests/test_qt_generation.py)。

## 验收标准

1. 未启用 Qt 插件时，Qt 生成入口不可用或给出启用提示，且不写入目标文件。
2. 启用 Qt 插件但缺少 Qt SDK、CMake 或编译器时，输出包含缺失项、检查命令、配置路径或关闭插件建议。
3. 启用 Qt 插件后，合法项目名和空目标目录能生成最小 Qt Widgets + CMake 项目。
4. dry-run 能列出将写入文件清单且不创建目标目录，并写入可 trace inspect 读取的 Qt artifact。
5. Qt smoke validation 覆盖结构检查和 CMake 项目识别；真实 Qt 5.14.2 构建在环境存在时执行，否则记录 skip 原因。
6. 长任务 evidence / handoff / read_before_start 可支撑清空上下文后的恢复。

## 检查方法

- 读取任务条目：[tasks-p9.md:41-44](../../tasks-p9.md#L41-L44)。
- 读取实现自检：[p9_qt_implementation_check.md](p9_qt_implementation_check.md)。
- 读取 QA 相关测试：
  - [test_cli_smoke.py:257-279](../../tests/test_cli_smoke.py#L257-L279)
  - [test_cli_smoke.py:282-311](../../tests/test_cli_smoke.py#L282-L311)
  - [test_cli_smoke.py:313-340](../../tests/test_cli_smoke.py#L313-L340)
  - [test_cli_smoke.py:343-365](../../tests/test_cli_smoke.py#L343-L365)
  - [test_cli_smoke.py:368-381](../../tests/test_cli_smoke.py#L368-L381)
  - [test_qt_generation.py:15-86](../../tests/test_qt_generation.py#L15-L86)
- 执行命令：

```bash
python -m pytest tests/test_cli_smoke.py::test_generate_qt_requires_enabled_plugin_without_writing tests/test_cli_smoke.py::test_project_types_list_reports_qt_environment_diagnostics tests/test_cli_smoke.py::test_generate_qt_prints_dependency_diagnostics_without_blocking tests/test_cli_smoke.py::test_generate_qt_dry_run_lists_files_without_writing tests/test_cli_smoke.py::test_generate_qt_writes_rendered_files tests/test_qt_generation.py
```

结果：`7 passed, 1 skipped in 3.20s`。

## 结果记录

| 标准 | 结果 | 证据 |
| --- | --- | --- |
| 未启用 Qt 插件时阻止生成且不写文件 | 通过 | [test_cli_smoke.py:368-381](../../tests/test_cli_smoke.py#L368-L381) 断言 `SystemExit(1)`、提示“未启用”、目标目录不存在；QA 命令通过 |
| 启用但缺依赖时输出结构化/可读诊断 | 通过 | [test_cli_smoke.py:257-279](../../tests/test_cli_smoke.py#L257-L279) 验证 JSON `environment_diagnostics.qt` 含 `qt5/missing/Qt5_DIR`；[test_cli_smoke.py:282-311](../../tests/test_cli_smoke.py#L282-L311) 验证输出含“Qt 环境诊断”和 `cmake --version` |
| 启用后生成最小 Qt Widgets + CMake 项目 | 通过 | [test_cli_smoke.py:343-365](../../tests/test_cli_smoke.py#L343-L365) 验证生成成功、`CMakeLists.txt` 含 `find_package(Qt5 5.14 REQUIRED COMPONENTS Widgets)`、源文件无占位符残留 |
| dry-run 不写目标目录且 artifact 可见 | 通过 | [test_cli_smoke.py:313-340](../../tests/test_cli_smoke.py#L313-L340) 验证 `dry_run=True`、planned files 含 `CMakeLists.txt`、generated_files 为空、`.opc_state.json` 和 `trace_inspect` 均能看到 `qt_generation` artifact |
| 结构 smoke 与 CMake 项目识别 | 通过 | [test_qt_generation.py:15-45](../../tests/test_qt_generation.py#L15-L45) 验证文件清单、Qt5 5.14 Widgets CMake 内容、占位符清理和 CMake build command 检测 |
| 真实 Qt 5.14.2 构建验证或 skip 原因 | 通过 | [test_qt_generation.py:48-86](../../tests/test_qt_generation.py#L48-L86) 在缺少必需 Qt/CMake/compiler 环境时输出 skip 原因；本次 QA 命令结果为 `1 skipped` |
| 长任务可恢复性 | 通过 | [tasks-p9.md:41-44](../../tasks-p9.md#L41-L44) 已记录 P9-QT-12 至 P9-QT-14 的 evidence/handoff；本报告完成后 P9-QT-15 会写回 evidence/handoff |

## 是否通过

结论：通过。

未通过项：无。

可恢复性结论：可清空上下文继续。任务条目、实现自检报告、QA 验收报告、测试名称和关键文件路径均已记录；下一步可进入 P9-DOC-01 更新 README Qt 生成说明。

备注：真实 Qt 5.14.2 构建未在当前机器执行成功，因为本机缺少完整 Qt/CMake/compiler 链路；测试按 P9 验收规则记录 skip 原因，此项不阻塞 QA 通过。
