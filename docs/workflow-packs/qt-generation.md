# Qt Generation Workflow Pack

## Manifest

| 字段 | 值 |
| --- | --- |
| `id` | `qt-generation` |
| `kind` | `opc_runtime_workflow` |
| `owner_roles` | `Architect`, `Engineer`, `Ops`, `QA` |
| `inputs` | Qt 生成任务描述、project name、target dir、template id、Qt 插件启用状态、环境诊断、验收标准 |
| `outputs` | Qt Widgets + CMake 生成文件清单、环境检测摘要、构建验证结果、QA 验收记录、run artifacts |
| `permissions` | 允许读取 Qt PRD、插件 manifest 和模板；允许写入目标生成目录和 run artifacts；允许运行定向生成、环境检测和验证命令；危险操作需要人工确认 |
| `acceptance` | Qt 插件边界清晰，生成文件完整，缺依赖诊断可读，构建验证执行或记录 skip 原因，QA 覆盖三类核心场景 |
| `trace` | stage_started、project_type_selected、environment_checked、files_planned、files_generated、build_validated、qa_completed、approval_decision |

## 适用场景

- 用户要求 OPC 生成最小 Qt Widgets + CMake 项目，并希望结果进入 run trace / artifacts。
- Qt 插件已启用，或用户明确要验证 Qt 插件启用、生成和环境诊断链路。
- 任务需要把 `opc project-types list`、`opc generate qt`、结构 smoke、可选真实构建和 QA 验收串成可复盘流程。

## 不适用场景

- 只需要手动执行一次模板生成且不需要 run artifacts，可直接使用 `opc generate qt`。
- 需要 QML、qmake、Qt Designer `.ui`、资源系统或 Qt6 验收，应拆分为后续 Qt 模板扩展 pack。
- 需要自动安装 Qt SDK、CMake、MSVC、MinGW 或修改系统 PATH；这些动作必须由用户在本机环境中确认和执行。
- 未启用 Qt 插件且用户没有要求生成 Qt 项目时，不应触发 Qt 环境检测。

## 角色边界

| 角色 | 责任 | 禁止事项 |
| --- | --- | --- |
| Architect | 确认 project type、插件 manifest、模板 id、权限和 workflow 边界符合 Qt 5.14.2 + Widgets + CMake 第一版范围 | 不把 QML、qmake、Qt6 或插件市场能力纳入 P9 验收 |
| Engineer | 执行项目类型发现、dry-run、模板生成和最小构建验证，记录生成文件清单与失败点 | 不覆盖已有用户文件，不绕过插件启用边界，不用 LLM 临时生成关键构建文件 |
| Ops | 检查 CMake、Qt5、编译器、generator 和路径一致性诊断，给出可执行的本机配置提示 | 不自动安装依赖，不修改全局 PATH、系统配置或共享环境 |
| QA | 验收未启用插件、启用但缺依赖、启用且生成最小项目三类场景，输出 pass/fail 和证据 | 不把真实构建缺环境 skip 判定为失败，也不在缺少 skip 原因时判定通过 |

## 输入要求

- `project_name`：合法 Qt 项目名，用于渲染 `project_name`、`executable_name` 和 `class_name`。
- `target_dir`：目标生成目录；必须位于用户授权范围内，且默认不得覆盖已有文件。
- `template_id`：第一版固定为 `widgets-cmake`。
- `plugin_state`：Qt 插件是否通过 `plugins.enabled = ["qt"]` 或等价环境配置启用。
- `environment_diagnostics`：`cmake`、`qt5`、`compiler`、`cmake-generator`、`qt-path-consistency` 的结构化结果。
- `acceptance_criteria`：生成文件完整性、环境诊断、构建验证或 skip、QA 覆盖范围。

## 输出要求

- `project_type_summary`：选中的 project type、plugin id、template id 和权限声明。
- `generation_plan`：dry-run 文件清单、目标目录、冲突检查和安全写入结论。
- `generated_files`：实际写入文件的相对路径，至少包含 `CMakeLists.txt`、`src/main.cpp`、`src/MainWindow.h`、`src/MainWindow.cpp`。
- `environment_report`：结构化环境诊断，包含缺失项、检查命令、配置路径建议和关闭 Qt 插件方式。
- `build_validation`：`tests/test_qt_generation.py` 结构 smoke 结果，以及真实 Qt 5.14.2/CMake 构建结果或 skip 原因。
- `qa_report`：三类核心场景的检查结果、证据、blocking defects 和最终 `pass` / `fail` / `needs-info` 结论。

## 权限边界

- 默认允许读取 `docs/plan/qt-generation-prd.md`、`plugins/qt/opc-plugin.toml`、`templates/qt/widgets-cmake/`、相关测试和当前项目配置。
- 允许写入目标生成目录中的模板文件、当前 run 的 `artifacts/`、Engineer 输出和 QA 验收记录。
- 允许运行定向命令：`opc project-types list`、`opc project-types list --json`、`opc generate qt --dry-run`、`opc generate qt`、`python -m pytest tests/test_qt_generation.py`，以及环境可用时的 `cmake -S . -B build` 和 `cmake --build build`。
- 覆盖已有文件、删除生成目录、修改全局环境变量、安装/卸载依赖、push、发布或访问共享基础设施必须人工确认。

## 验收标准

- 未启用 Qt 插件时，Qt 生成入口不可用或给出启用提示，且不写入文件、不检查 Qt 环境。
- 启用 Qt 插件但缺 Qt SDK、CMake 或编译器时，诊断包含缺失项、检查命令、`Qt5_DIR` / `CMAKE_PREFIX_PATH` 等配置路径和从 `plugins.enabled` 移除 `qt` 的关闭方式。
- 合法项目名和空目标目录下，`widgets-cmake` 生成完整 Qt Widgets + CMake 文件清单，且渲染后无模板占位符残留。
- dry-run 只展示将写入文件清单，不创建目标文件。
- `tests/test_qt_generation.py` 结构 smoke 通过；真实 Qt 5.14.2 构建在环境满足时执行，否则记录可读 skip 原因。
- QA 报告至少覆盖未启用 Qt 插件、启用但缺环境、启用且生成最小项目三类场景，并给出明确结论。

## Trace / Artifact 要求

- `run_events.jsonl`：记录 project type 发现、环境检测、dry-run 文件计划、模板写入、构建验证和 QA 阶段事件。
- `run_trace.json`：记录插件启用状态、template id、人工确认、失败点、skip 原因、QA 退回和最终状态。
- `artifacts`：保存生成文件清单、环境诊断 JSON、构建/pytest 输出摘要、Engineer 实现记录和 QA 验收报告。

## 转交规则

- 插件未启用且用户只想了解能力：转 docs-update 或只读说明，不执行生成。
- 生成文件、CLI 或诊断行为不符合 pack 验收：转 bugfix pack，要求最小修复和定向验证。
- 需要把生成结果稳定写入 run artifacts：转 P9-QT-13 对应实现任务。
- QA 通过后若需要用户文档和 walkthrough：转 docs-update pack 或 P9-DOC-01 / P9-DOC-03。
- 用户要求 QML、qmake、Qt6 或自动安装依赖：回退 PM/Architect 重新定义范围。
