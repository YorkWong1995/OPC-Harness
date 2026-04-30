# 新工具使用指南

本文档说明 OPC 新增的三个工具及其使用方法。

## 1. edit_file 工具（diff 模式编辑）

### 功能
用 `new_string` 替换 `old_string`，只发送 diff 而非整个文件，节省 50-90% token。

### 参数
- `path`: 文件路径（相对于项目根目录）
- `old_string`: 要替换的原始字符串（必须在文件中存在）
- `new_string`: 替换后的新字符串
- `replace_all`: 是否替换所有匹配项（默认 false，只替换第一个）

### 使用示例

```python
# 示例 1: 添加类型注解
edit_file(
    path="auth.py",
    old_string="def login(username, password):",
    new_string="def login(username: str, password: str) -> bool:",
)

# 示例 2: 批量替换
edit_file(
    path="config.py",
    old_string="DEBUG = True",
    new_string="DEBUG = False",
    replace_all=True,  # 替换所有匹配项
)

# 示例 3: 修改多行代码
edit_file(
    path="main.py",
    old_string="""def process_data(data):
    return data.strip()""",
    new_string="""def process_data(data: str) -> str:
    \"\"\"处理输入数据\"\"\"
    return data.strip().lower()""",
)
```

### 优势对比

**使用 write_file（旧方式）**：
```python
# 需要发送整个文件（500 行 = ~2000 tokens）
write_file(path="auth.py", content="<整个文件 500 行>")
```

**使用 edit_file（新方式）**：
```python
# 只发送 diff（~50 tokens）
edit_file(
    path="auth.py",
    old_string="def login(username, password):",
    new_string="def login(username: str, password: str) -> bool:",
)
```

**Token 节省**：~97%（2000 → 50）

---

## 2. grep 工具（快速搜索）

### 功能
搜索文件内容，支持正则表达式。优先使用 ripgrep（快 10-100 倍），自动回退到 Python re。

### 参数
- `pattern`: 正则表达式搜索模式
- `file_glob`: 文件过滤 glob 模式（默认 `**/*`）
- `case_sensitive`: 是否区分大小写（默认 true）
- `limit`: 最大返回结果数（默认 200）

### 使用示例

```python
# 示例 1: 查找 TODO 注释
grep(pattern="TODO")
# 输出：
# src/auth.py:42:# TODO: Add rate limiting
# src/api.py:15:# TODO: Implement caching

# 示例 2: 查找函数定义（正则）
grep(pattern="def \\w+\\(", file_glob="**/*.py")
# 输出：
# src/auth.py:10:def login(username, password):
# src/auth.py:25:def logout(session_id):

# 示例 3: 不区分大小写搜索
grep(pattern="error", case_sensitive=False)
# 输出：
# src/logger.py:5:ERROR = "error"
# src/main.py:42:raise ValueError("Error occurred")

# 示例 4: 只搜索特定文件类型
grep(pattern="import", file_glob="**/*.py", limit=50)

# 示例 5: 查找配置项
grep(pattern="API_KEY|SECRET", file_glob="**/*.env")
```

### 性能对比

| 场景 | Python re | Ripgrep | 提升 |
|---|---|---|---|
| 小项目（100 文件） | 0.5 秒 | 0.05 秒 | 10x |
| 中型项目（1000 文件） | 5 秒 | 0.2 秒 | 25x |
| 大型项目（10000 文件） | 50 秒 | 0.5 秒 | 100x |

**安装 ripgrep**（可选，但强烈推荐）：
- Windows: `choco install ripgrep` 或 `scoop install ripgrep`
- macOS: `brew install ripgrep`
- Linux: `apt install ripgrep` 或 `yum install ripgrep`

---

## 3. run_command 工具（改进版）

### 新增功能
1. **交互式命令检测**：自动检测 `npm create`、`yarn init` 等交互式命令，提前拒绝避免卡死
2. **异步执行**：支持更长超时（默认 300 秒，可配置）
3. **更好的错误处理**：超时时优雅终止进程，返回部分输出
4. **输出截断**：12000 字符（原 5000）

### 参数
- `command`: 要执行的命令
- `timeout`: 超时时间（秒，默认 300）

### 使用示例

```python
# 示例 1: 正常命令
run_command(command="pytest tests/")
# 输出：
# ============================= test session starts ==============================
# collected 42 items
# tests/test_auth.py ........                                              [ 19%]
# tests/test_api.py ..........                                             [ 42%]
# ...

# 示例 2: 交互式命令（会被拒绝）
run_command(command="npm create vite@latest")
# 输出：
# 错误：此命令需要交互式输入，但 run_command 工具不支持交互。
# 建议：添加非交互式标志（如 --yes、-y、--defaults、--non-interactive）。
# 示例：npm create vite@latest --yes

# 示例 3: 使用非交互式标志
run_command(command="npm create vite@latest my-app -- --template react")
# 输出：
# Scaffolding project in /path/to/my-app...
# Done. Now run:
#   cd my-app
#   npm install
#   npm run dev

# 示例 4: 长时间命令（自定义超时）
run_command(command="npm run build", timeout=600)  # 10 分钟超时

# 示例 5: Git 操作
run_command(command="git status")
run_command(command="git log --oneline -10")
```

### 交互式命令检测列表

以下命令会被自动检测并拒绝（除非添加非交互式标志）：

- `npm create`、`npm init`
- `pnpm create`、`pnpm init`
- `yarn create`、`yarn init`
- `bun create`
- `npx create-*`、`bunx create-*`
- `cargo new`、`cargo init`

**解决方法**：添加非交互式标志
- `npm create vite@latest --yes`
- `npm init -y`
- `cargo new my-project --bin`

---

## 工具选择建议

### 修改代码时
1. **优先使用 edit_file**：节省 token，速度快
2. **只在以下情况使用 write_file**：
   - 创建新文件
   - 完全重写文件（改动超过 50%）

### 搜索代码时
1. **优先使用 grep**：快速、支持正则
2. **只在以下情况使用 read_file**：
   - 需要读取完整文件内容
   - 需要理解上下文

### 执行命令时
1. **注意交互式命令**：添加 `--yes`、`-y` 等标志
2. **长时间命令**：设置合适的 `timeout`
3. **白名单限制**：只能执行 `python`、`pip`、`npm`、`node`、`git`、`pytest`、`eslint`、`npx`、`cargo`、`go`

---

## 完整示例：修复一个 Bug

```python
# 1. 搜索 Bug 位置
grep(pattern="UserNotFoundError")
# 输出：src/auth.py:42:raise UserNotFoundError("User not found")

# 2. 读取相关代码
read_file(path="src/auth.py")

# 3. 修改代码（使用 edit_file）
edit_file(
    path="src/auth.py",
    old_string='raise UserNotFoundError("User not found")',
    new_string='logger.error(f"User {username} not found")\nraise UserNotFoundError(f"User {username} not found")',
)

# 4. 运行测试
run_command(command="pytest tests/test_auth.py -v")

# 5. 检查是否还有其他地方需要修改
grep(pattern="UserNotFoundError", file_glob="**/*.py")
```

---

## 性能提升总结

| 操作 | 旧方式 | 新方式 | 提升 |
|---|---|---|---|
| 修改一行代码 | write_file（2000 tokens） | edit_file（50 tokens） | 40x |
| 搜索关键词 | 逐个 read_file | grep（ripgrep） | 10-100x |
| 执行命令 | 可能卡死 | 交互式检测 | 避免卡死 |

---

## 常见���题

### Q1: edit_file 报错 "old_string 不存在"
**原因**：`old_string` 必须完全匹配文件中的内容（包括空格、缩进）。

**解决**：
1. 先用 `read_file` 读取文件，复制准确的内容
2. 确保缩进、空格完全一致

### Q2: grep 搜索不到结果
**原因**：
1. 正则表达式错误
2. 文件被 `.gitignore` 排除
3. 文件在排除目录（`__pycache__`、`.git`、`node_modules`、`.venv`）

**解决**：
1. 测试正则表达式：`grep(pattern="test")`（简单搜索）
2. 检查文件路径：`list_files(pattern="**/*.py")`

### Q3: run_command 超时
**原因**：命令执行时间超过 300 秒。

**解决**：
1. 增加 `timeout` 参数：`run_command(command="...", timeout=600)`
2. 检查命令是否卡在交互式输入

---

## 下一步

建议安装 ripgrep 以获得最佳性能：
```bash
# Windows
choco install ripgrep

# macOS
brew install ripgrep

# Linux
apt install ripgrep
```

验证安装：
```bash
rg --version
```
