# Qt 项目生成 PRD

## 1. 背景

OPC 当前定位是面向单人本地开发者的软件交付编排层，核心能力围绕结构化角色协作、run trace、知识检索和可验证交付闭环。P9 的目标是在不加重核心 runtime 的前提下，让 OPC 能可靠生成可构建、可验收的 Qt 项目，并为后续项目类型扩展提供插件化基础。

Qt 生成能力的第一版需要解决两个问题：

- 用户希望通过 OPC 快速得到一个结构稳定、可本地构建的 Qt 起步项目，而不是依赖 LLM 临时拼接关键构建文件。
- 不使用 Qt 的用户不应被 Qt SDK、CMake、编译器或模板依赖影响，核心 OPC run 仍保持轻量。

第一版目标 Qt 环境以 **Qt 5.14.2** 为验收基准；Qt6 兼容只作为后续扩展方向，不作为 P9 第一版通过条件。

## 2. 目标

1. 支持按需启用 Qt 项目生成能力，未启用时不加载 Qt 模板、不检查 Qt 环境、不影响普通 OPC 工作流。
2. 提供最小 Qt Widgets + CMake 项目模板，生成后包含完整源文件、构建文件和可复现的后续构建命令。
3. 在生成前明确将写入的文件清单，并在冲突、非法项目名或路径不安全时拒绝写入。
4. 提供 Qt 5.14.2 / CMake / 编译器环境检测规则和可读诊断，帮助用户定位缺失依赖或配置路径问题。
5. 为 QML、qmake 和后续语言/项目类型扩展保留插件边界，但不在第一版过度实现。

## 3. 用户场景

### 3.1 生成最小 Qt Widgets 项目

用户已经安装 Qt 5.14.2 与 CMake，希望在指定目录生成一个最小桌面窗口项目，用于后续人工开发或交给 OPC 继续迭代。

期望流程：

1. 启用 Qt project plugin。
2. 查看可用项目类型和模板。
3. 执行 Qt 生成命令，指定项目名、目标目录和模板类型。
4. 查看将写入文件清单。
5. 生成项目并按提示运行 CMake 构建命令。

### 3.2 未安装 Qt 时了解缺失项

用户想试用 Qt 生成，但本机缺少 Qt 5.14.2、CMake 或编译器。

期望结果：

- OPC 能生成结构检查或 dry-run 信息。
- 环境检测报告明确缺少哪些项、建议检查命令和可配置路径。
- 缺失 Qt 环境不会影响非 Qt 项目类型或普通 `opc run`。

### 3.3 普通 OPC 用户不使用 Qt

用户只使用 PM → Engineer → QA 工作流、知识检索或其他项目类型。

期望结果：

- 默认配置不要求安装 Qt 插件。
- `opc doctor`、`opc run`、`opc query` 等核心能力不触发 Qt 检测。
- 项目类型发现只展示已启用能力，禁用插件不会暴露误导性 Qt 入口。

## 4. 功能范围

### 4.1 第一版支持

| 能力 | 第一版结论 | 说明 |
| --- | --- | --- |
| Qt Widgets | 支持 | 提供最小窗口应用模板，作为第一版唯一 Qt UI 模板。 |
| Qt 5.14.2 | 支持并作为验收基准 | 模板和环境检测优先匹配 Qt5，尤其是 Windows 本机 Qt 5.14.2 安装路径。 |
| CMake | 支持 | 作为第一版默认且唯一构建系统，生成 `CMakeLists.txt`。 |
| QML | 不实现，仅预留 | PRD 和架构中保留模板扩展点，但不生成 QML 项目。 |
| qmake | 不实现，仅说明不支持 | 第一版不生成 `.pro` 文件，避免同时维护两套构建链路。 |
| Qt6 | 不作为 P9 验收前提 | 可在设计上避免阻断未来 Qt6，但第一版不承诺 Qt6 smoke 通过。 |
| Windows 本机 | 重点覆盖 | 环境检测需关注 Qt 5.14.2 SDK、CMake、MSVC/MinGW、`CMAKE_PREFIX_PATH` / `Qt5_DIR`。 |
| 插件启用 | 支持 | Qt 能力通过 plugin/project pack 启用，不进入默认核心能力。 |
| dry-run | 支持 | 生成前展示文件清单，不写入文件。 |
| 安全写入 | 支持 | 拒绝非法项目名、路径穿越和未确认覆盖。 |

### 4.2 生成文件范围

最小 Qt Widgets + CMake 模板至少包含：

- `CMakeLists.txt`
- `src/main.cpp`
- `src/MainWindow.h`
- `src/MainWindow.cpp`
- 可选 `README.md` 或生成说明文件由后续任务决定；第一版不依赖该文件完成构建。

### 4.3 CLI 范围

第一版可以采用以下任一等价入口，最终以实现任务落地为准：

- `opc project-types list`：只读列出已启用项目类型、模板、环境状态和启用提示。
- `opc generate qt --name <project-name> --target-dir <dir> --template widgets-cmake`：生成 Qt 项目。
- 或 `opc run --project-type qt` 的最小入口；若采用该入口，必须保证不调用模型也能完成模板生成的基础路径。

### 4.4 环境检测规则

Qt 环境检测只在 Qt 插件已启用且用户执行 `opc project-types list`、`opc generate qt`、Qt workflow pack 或显式环境检查时运行；未启用 Qt 插件时不检查 Qt/CMake/编译器。

| 检查项 | 等级 | 检测方式 | Windows 本机提示 |
| --- | --- | --- | --- |
| CMake | 必需 | `cmake --version`，版本需满足模板 `cmake_minimum_required` | 未找到时提示安装 CMake 并确认 `cmake` 在 PATH 中 |
| Qt 5.14.2 / Qt5 SDK | 必需 | 查找 `Qt5Config.cmake`，优先读取 `Qt5_DIR`，其次读取 `CMAKE_PREFIX_PATH`，再检查常见 Qt 安装目录 | 提示配置 `Qt5_DIR=<Qt>/lib/cmake/Qt5` 或 `CMAKE_PREFIX_PATH=<Qt>`，例如 `C:/Qt/5.14.2/msvc2017_64` 或 `C:/Qt/5.14.2/mingw73_64` |
| C++ 编译器 | 必需 | 检查 MSVC `cl` 或 MinGW `g++` 是否可用 | MSVC 提示从 Developer Command Prompt 启动；MinGW 提示确认 Qt kit 对应的 `bin` 在 PATH 中 |
| CMake generator | 建议 | 根据编译器识别 Visual Studio、Ninja、MinGW Makefiles 等可用 generator | 缺 generator 不阻断结构生成，但真实构建需提示可尝试 `-G` 参数 |
| Qt 路径一致性 | 建议 | 检查 Qt kit 路径是否与编译器族一致，例如 MSVC Qt kit 对 MSVC、MinGW Qt kit 对 MinGW | 不一致时提示切换 Qt kit、编译器或 `CMAKE_PREFIX_PATH` |

缺依赖诊断必须包含：缺失项、建议检查命令、可配置路径、关闭 Qt 插件方式，以及“不影响普通 OPC run / 其他 project type”的说明。环境检测不自动安装 Qt SDK、CMake、MSVC 或 MinGW。

## 5. 非目标

1. 不实现完整 Qt Designer、`.ui` 文件、资源系统和国际化流程。
2. 不实现 QML 项目生成；仅在架构和模板目录上保留扩展点。
3. 不实现 qmake 项目生成；第一版统一使用 CMake。
4. 不自动安装 Qt SDK、CMake、MSVC、MinGW 或第三方依赖。
5. 不在核心 runtime 默认加载 Qt 插件或执行 Qt 环境检测。
6. 不保证所有 Qt 版本和所有 CMake generator 组合都能真实构建；P9 第一版以 Qt 5.14.2 + CMake 的本机验证或明确 skip 证据为准。
7. 不引入长期后台服务、远程构建、CI 托管或企业级多用户插件市场。
8. 不用 LLM 生成关键构建文件；模板应来自版本化文件。

## 6. 验收标准

### 6.1 产品验收

- PRD 明确第一版支持 Qt Widgets + CMake，并以 Qt 5.14.2 作为目标验收环境。
- PRD 明确 QML 和 qmake 不在第一版范围。
- README 或后续用户文档能说明如何启用 Qt 插件、生成项目、检查环境和处理缺依赖。
- 未启用 Qt 插件时，普通 OPC 使用路径不要求 Qt 环境。

### 6.2 生成验收

- 给定合法项目名和空目标目录，生成结果包含最小 Qt Widgets + CMake 项目文件。
- dry-run 能输出将写入文件清单且不创建文件。
- 目标文件已存在时默认拒绝覆盖，并返回可读冲突信息。
- 非法项目名、路径穿越或目标目录逃逸时拒绝写入。

### 6.3 插件与发现验收

- project type registry 能表达 Qt 项目类型及未来 Python/Node/Rust/Embedded 等项目类型。
- 禁用 Qt 插件时，Qt 生成入口不可用或给出启用提示。
- 启用 Qt 插件时，项目类型发现能展示 Qt、模板 id、环境检测摘要和构建建议。

### 6.4 环境与构建验收

- 环境检测能报告 CMake、Qt 5.14.2/Qt5、编译器和 Qt 路径配置状态。
- 缺依赖时提示包含缺失项、建议检查命令、配置路径建议和关闭插件的方式。
- CMake 项目能被 build command 检测识别，不破坏既有 Python/Node/Rust 检测路径。
- Qt smoke validation 至少覆盖不依赖真实 Qt SDK 的生成结构检查；真实 Qt 5.14.2 构建在环境存在时执行，否则记录 skip 原因。

### 6.5 可观测与验收报告

- Qt 生成过程应能写入 run artifacts 或等价 trace，至少包含 project type、template id、生成文件清单、环境检测摘要和构建验证结果。
- implementation-check 能确认实现范围未偏离 PRD，尤其是插件可选性和核心轻量性。
- acceptance-check 能覆盖未启用 Qt 插件、启用但缺环境、启用且生成最小项目三类场景。

## 7. 风险与约束

| 风险 | 影响 | 应对方式 |
| --- | --- | --- |
| Qt 环境组合复杂 | 真实构建可能因用户本机 Qt/CMake/编译器组合失败 | 第一版固定以 Qt 5.14.2 为目标，区分结构验证与真实环境构建，真实构建可 skip 并记录原因。 |
| 插件边界不清 | Qt 能力可能污染核心 runtime | registry 默认只展示已启用插件，Qt 检测仅在插件启用或显式命令时触发。 |
| 模板覆盖用户文件 | 可能破坏已有项目 | 生成前列出文件，默认拒绝覆盖，路径安全检查必须先于写入。 |
| 同时支持 QML/qmake 造成过度设计 | 增加维护成本并拖慢第一版 | 第一版只做 Widgets + CMake，QML/qmake 仅记录为后续扩展。 |
| CLI 入口过早绑定 runtime workflow | 可能让简单模板生成被模型调用拖慢 | 项目类型发现和模板生成应提供不调用模型的只读/写入路径。 |

## 8. 后续扩展方向

1. 增加 QML 模板 pack，并补充 QML-specific 环境与 smoke validation。
2. 增加 `.ui` / resource system 模板选项。
3. 增加 Qt6 compatibility validation，独立于 Qt 5.14.2 第一版验收。
4. 增加非 Qt project type 样例插件，验证 registry 不是 Qt 专用。
5. 将生成、环境检测、构建和 QA 结果稳定写入 trace inspect 可读取的 artifacts。
