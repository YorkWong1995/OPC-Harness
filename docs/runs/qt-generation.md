# Qt Generation Walkthrough

## 目标

本 walkthrough 演示如何在 OPC 中启用可选 Qt 插件，生成最小 Qt 5.14.2 Widgets + CMake 项目，并查看环境诊断、生成文件清单和 trace artifact。

适用范围：Qt 5.14.2、Qt Widgets、CMake、`widgets-cmake` 模板。QML、qmake、Qt Designer `.ui`、Qt6 验收和自动安装依赖不属于 P9 第一版范围。

## 前置条件

- 已安装 OPC 并在项目根目录执行过 `opc init`。
- 需要生成 Qt 项目时，才启用 Qt 插件；不需要 Qt 的用户无需安装 Qt SDK、CMake 或编译器。
- 如需真实构建，需要本机具备 Qt 5.14.2、CMake 和匹配的 C++ 编译器；缺失时 walkthrough 仍可执行 dry-run 和结构生成，并按诊断提示处理。

## 1. 启用 Qt 插件

在 `opc.toml` 中启用 Qt project type：

```toml
[plugins]
enabled = ["qt"]

[plugins.qt]
enabled = true
manifest_path = "plugins/qt/opc-plugin.toml"
templates = ["widgets-cmake"]
qt_version = "5.14.2"
qt_dir = ""
cmake_prefix_path = ""
```

关闭方式：从 `plugins.enabled` 移除 `"qt"`，或将 `[plugins.qt].enabled` 设为 `false`。关闭后核心 OPC 命令不会检查 Qt SDK、CMake 或编译器。

## 2. 检查项目类型和环境诊断

```bash
opc project-types list
opc project-types list --json
```

预期结果：

- 已启用时能看到 `qt` / `Qt Widgets` project type 和 `widgets-cmake` 模板。
- 缺少 Qt SDK、CMake 或编译器时，诊断包含缺失项、检查命令、配置路径建议和关闭插件方式。
- 常见检查命令包括 `cmake --version`、Qt5 配置路径检查和编译器探测。

常见配置路径：

- `Qt5_DIR`：指向 Qt 5.14.2 的 `Qt5Config.cmake` 所在目录。
- `CMAKE_PREFIX_PATH`：指向 Qt kit 前缀目录。
- `PATH`：包含 CMake、MSVC Developer Command Prompt 或 MinGW 工具链路径。

## 3. dry-run 查看文件清单

```bash
opc generate qt --name DemoQtApp --target-dir workspace/DemoQtApp --dry-run
```

预期结果：

- 输出将写入的文件清单。
- 不创建 `workspace/DemoQtApp` 目标目录。
- 写入项目级 `artifacts/qt_generation.json`、`artifacts/run_events.jsonl`、`artifacts/run_trace.json` 和 `artifacts/.opc_state.json`。
- `qt_generation.json` 中 `dry_run` 为 `true`，`planned_files` 至少包含 `CMakeLists.txt`，`generated_files` 为空。

## 4. 生成最小 Qt Widgets + CMake 项目

```bash
opc generate qt --name DemoQtApp --target-dir workspace/DemoQtApp
```

预期文件：

```text
workspace/DemoQtApp/
├── CMakeLists.txt
└── src/
    ├── main.cpp
    ├── MainWindow.cpp
    └── MainWindow.h
```

预期内容：

- `CMakeLists.txt` 包含 `find_package(Qt5 5.14 REQUIRED COMPONENTS Widgets)`。
- `src/main.cpp` 使用 `QApplication` 启动 Qt Widgets 应用。
- 渲染结果不应残留 `{{ ... }}` 模板占位符。
- 若目标文件已存在，生成默认拒绝覆盖，需要用户先选择新的空目录或人工处理冲突。

## 5. 构建验证

环境完整时，在生成目录执行：

```bash
cmake -S workspace/DemoQtApp -B workspace/DemoQtApp/build
cmake --build workspace/DemoQtApp/build
```

如果本机缺少 Qt 5.14.2、CMake 或编译器，真实构建可以跳过，但必须记录原因。P9 验收允许在缺环境时以 skip 证据替代真实构建成功，前提是结构 smoke、CMake 项目识别和诊断输出通过。

## 6. 查看 trace artifact

```bash
opc trace inspect --artifacts-dir artifacts
```

预期结果：

- `artifacts.qt_generation` 指向 `artifacts/qt_generation.json`。
- timeline 中能看到 project type 选择、环境检测、文件计划、文件生成或 dry-run、构建验证状态。
- `qt_generation.json` 记录 `project_type=qt`、`template_id=widgets-cmake`、`target_dir`、`dry_run`、`planned_files`、`generated_files`、`environment_diagnostics` 和 `build_validation`。

## 7. 常见失败原因和处理方式

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `Qt project type 未启用` | `plugins.enabled` 未包含 `qt` | 按第 1 步启用插件，或确认当前任务不需要 Qt |
| `qt5` 诊断为 `missing` | 找不到 Qt 5.14.2 / `Qt5Config.cmake` | 配置 `Qt5_DIR` 或 `CMAKE_PREFIX_PATH`，确认安装的是 Qt 5.14.2 kit |
| `cmake` 诊断为 `missing` | CMake 不在 PATH | 安装 CMake 或把 `cmake` 加入 PATH 后重跑 `cmake --version` |
| `compiler` 诊断为 `missing` | 找不到 MSVC `cl` 或 MinGW `g++` | 使用 Developer Command Prompt，或把匹配 Qt kit 的 MinGW 加入 PATH |
| 生成拒绝覆盖 | 目标目录已有同名文件 | 使用空目录，或人工确认后清理冲突文件 |
| 真实构建 skip | 本机缺少完整 Qt/CMake/compiler 链路 | 记录 skip 原因；在具备环境的机器上补跑 CMake configure/build |

## 8. 验收标准

walkthrough 对齐 P9-QT-15 QA 验收结论：

1. 未启用 Qt 插件时，Qt 生成入口给出启用提示，且不写入目标文件。
2. 启用 Qt 插件但缺依赖时，输出缺失项、检查命令、配置路径或关闭插件建议。
3. 启用后，合法项目名和空目标目录能生成最小 Qt Widgets + CMake 项目。
4. dry-run 只列出 planned files，不创建目标目录，并写入 trace inspect 可见的 Qt artifact。
5. 结构 smoke 覆盖文件清单、Qt5 5.14 Widgets CMake 内容、占位符清理和 CMake build command 检测。
6. 真实 Qt 5.14.2 构建在环境存在时执行；环境缺失时记录 skip 原因。

## 9. 已验证证据

P9-QT-15 定向 QA 命令：

```bash
python -m pytest tests/test_cli_smoke.py::test_generate_qt_requires_enabled_plugin_without_writing tests/test_cli_smoke.py::test_project_types_list_reports_qt_environment_diagnostics tests/test_cli_smoke.py::test_generate_qt_prints_dependency_diagnostics_without_blocking tests/test_cli_smoke.py::test_generate_qt_dry_run_lists_files_without_writing tests/test_cli_smoke.py::test_generate_qt_writes_rendered_files tests/test_qt_generation.py
```

结果：`7 passed, 1 skipped`。skip 原因为当前机器缺少完整 Qt 5.14.2 / CMake / compiler 链路，此项按 P9 验收规则不阻塞通过。
