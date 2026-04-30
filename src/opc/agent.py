"""Agent 基类：封装 Claude API 调用与 tool use 循环"""

import subprocess
from pathlib import Path
import re
import shutil
import asyncio
import sys

import os

import anthropic

from .rag import SimpleRAG, create_rag_for_project
from .schema import Message, MessageQueue

# 允许 run_command 执行的命令白名单
COMMAND_WHITELIST = {
    "python", "pip", "npm", "node", "git", "pytest", "eslint", "npx", "cargo", "go",
    "gcc", "g++", "cmake", "make", "cl", "clang", "clang++", "nmake", "msbuild"
}


class Agent:
    """调用 Claude API 的角色 Agent，支持 tool use 和 RAG"""

    def __init__(
        self,
        role: str,
        system_prompt: str,
        tools: list[dict] | None = None,
        project_dir: Path | None = None,
        model: str | None = None,
        enable_rag: bool = False,
    ):
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools
        self.project_dir = project_dir
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        self.enable_rag = enable_rag
        self.rag: SimpleRAG | None = None

        # 消息缓冲区（用于 Environment 集成）
        self.msg_buffer = MessageQueue()

        # 初始化 RAG
        if enable_rag and project_dir:
            self.rag = create_rag_for_project(project_dir)

        # 支持中转地址：若设置了 ANTHROPIC_BASE_URL 则使用自定义端点
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        self.client = anthropic.Anthropic(
            base_url=base_url if base_url else None,
        )

    def receive(self, message: Message):
        """接收消息（用于 Environment 集成）"""
        self.msg_buffer.push(message)

    def has_pending_messages(self) -> bool:
        """检查是否有待处理的消息"""
        return bool(self.msg_buffer)

    def run(self, message: str) -> str:
        # 如果启用 RAG，先检索相关文档
        if self.rag:
            context = self.rag.get_context(message, max_tokens=2000)
            if context and context != "未找到相关文档。":
                print(f"[RAG][{self.role}] 检索到相关文档，添加到上下文")
                message = f"{message}\n\n---\n\n{context}"

        messages = [{"role": "user", "content": message}]

        while True:
            kwargs = {
                "model": self.model,
                "max_tokens": 4096,
                "system": self.system_prompt,
                "messages": messages,
                "timeout": 120.0,  # 120秒超时
            }
            if self.tools:
                kwargs["tools"] = self.tools

            try:
                response = self.client.messages.create(**kwargs)
            except anthropic.APITimeoutError as e:
                error_msg = f"[{self.role}] API 调用超时: {e}"
                print(error_msg)
                return error_msg
            except anthropic.APIError as e:
                error_msg = f"[{self.role}] API 调用错误: {e}"
                print(error_msg)
                return error_msg
            except Exception as e:
                error_msg = f"[{self.role}] 未知错误: {e}"
                print(error_msg)
                return error_msg

            # 收集响应中的内容块
            stop_reason = response.stop_reason
            assistant_content = response.content

            if stop_reason == "end_turn":
                return self._extract_text(assistant_content)

            if stop_reason == "tool_use":
                # 把 assistant 回复加入消息历史
                messages.append({"role": "assistant", "content": assistant_content})

                # 处理所有 tool_use 调用，收集结果
                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
                continue

            # 其他情况（如 max_tokens），返回已有文本
            return self._extract_text(assistant_content)

    def _extract_text(self, content: list) -> str:
        parts = []
        for block in content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)

    def _execute_tool(self, name: str, inputs: dict) -> str:
        dispatch = {
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
            "edit_file": self._tool_edit_file,
            "list_files": self._tool_list_files,
            "grep": self._tool_grep,
            "run_command": self._tool_run_command,
        }
        handler = dispatch.get(name)
        if not handler:
            return f"错误：未知工具 {name}"

        # 日志：工具调用开始
        print(f"[DEBUG][{self.role}] 执行工具: {name}")
        if name == "read_file":
            print(f"  -> 文件: {inputs.get('file_path', 'N/A')}")
        elif name == "write_file":
            print(f"  -> 文件: {inputs.get('file_path', 'N/A')}")
        elif name == "grep":
            print(f"  -> 模式: {inputs.get('pattern', 'N/A')}")
        elif name == "run_command":
            print(f"  -> 命令: {inputs.get('command', 'N/A')}")

        try:
            result = handler(**inputs)
            # 日志：工具调用成功
            result_preview = str(result)[:200] if result else "None"
            print(f"[DEBUG][{self.role}] 工具执行成功，结果预览: {result_preview}...")
            return result
        except Exception as e:
            error_msg = f"工具执行错误：{e}"
            print(f"[ERROR][{self.role}] {error_msg}")
            return error_msg

    def _tool_read_file(self, path: str) -> str:
        target = self._resolve_safe_path(path)
        if not target.exists():
            return f"错误：文件不存在 {path}"
        if target.is_dir():
            return f"错误：{path} 是目录，不是文件"
        return target.read_text(encoding="utf-8")

    def _tool_write_file(self, path: str, content: str) -> str:
        target = self._resolve_safe_path(path)
        # 安全边界：禁止写 .env 等敏感文件
        if target.name in {".env", ".env.local", ".env.production"}:
            return "错误：不允许写入环境变量文件"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"已写入 {path}（{len(content)} 字符）"

    def _tool_edit_file(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        """编辑文件：用 new_string 替换 old_string（diff 模式，节省 token）"""
        target = self._resolve_safe_path(path)
        if not target.exists():
            return f"错误：文件不存在 {path}"
        if target.is_dir():
            return f"错误：{path} 是目录，不是文件"

        # 安全边界：禁止编辑 .env 等敏感文件
        if target.name in {".env", ".env.local", ".env.production"}:
            return "错误：不允许编辑环境变量文件"

        try:
            original = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"错误：{path} 不是 UTF-8 文本文件"

        if old_string not in original:
            return f"错误：在文件中未找到 old_string。请确认要替换的内容存在。"

        # 执行替换
        if replace_all:
            count = original.count(old_string)
            updated = original.replace(old_string, new_string)
            target.write_text(updated, encoding="utf-8")
            return f"已更新 {path}（替换了 {count} 处）"
        else:
            updated = original.replace(old_string, new_string, 1)
            target.write_text(updated, encoding="utf-8")
            return f"已更新 {path}（替换了 1 处）"

    def _tool_list_files(self, pattern: str = "**/*") -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"
        matches = list(self.project_dir.glob(pattern))
        # 过滤掉 __pycache__、.git、node_modules 等
        skip = {"__pycache__", ".git", "node_modules", ".venv", "venv"}
        lines = []
        for p in sorted(matches):
            parts = p.relative_to(self.project_dir).parts
            if any(s in parts for s in skip):
                continue
            kind = "dir" if p.is_dir() else "file"
            lines.append(f"[{kind}] {p.relative_to(self.project_dir)}")
        return "\n".join(lines) if lines else "无匹配文件"

    def _tool_grep(self, pattern: str, file_glob: str = "**/*", case_sensitive: bool = True, limit: int = 200) -> str:
        """搜索文件内容：优先使用 ripgrep，回退到 Python re"""
        if not self.project_dir:
            return "错误：未设置项目目录"

        # 尝试使用 ripgrep（快速）
        rg_path = shutil.which("rg")
        if rg_path:
            try:
                cmd = [rg_path, "--line-number", "--no-heading", "--color", "never"]
                if not case_sensitive:
                    cmd.append("--ignore-case")
                cmd.extend(["--glob", file_glob, pattern, "."])

                result = subprocess.run(
                    cmd,
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")[:limit]
                    return "\n".join(lines) if lines else "无匹配结果"
                elif result.returncode == 1:
                    return "无匹配结果"
                else:
                    # ripgrep 出错，回退到 Python
                    pass
            except (subprocess.TimeoutExpired, Exception):
                # 超时或其他错误，回退到 Python
                pass

        # Python fallback（慢但可靠）
        try:
            regex = re.compile(pattern, flags=0 if case_sensitive else re.IGNORECASE)
        except re.error as e:
            return f"错误：无效的正则表达式 - {e}"

        matches = []
        skip = {"__pycache__", ".git", "node_modules", ".venv", "venv"}

        for file_path in self.project_dir.glob(file_glob):
            if not file_path.is_file():
                continue
            # 跳过排除目录
            parts = file_path.relative_to(self.project_dir).parts
            if any(s in parts for s in skip):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                for line_num, line in enumerate(content.splitlines(), start=1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(self.project_dir)
                        matches.append(f"{rel_path}:{line_num}:{line.strip()}")
                        if len(matches) >= limit:
                            break
            except (UnicodeDecodeError, PermissionError):
                # 跳过二进制文件或无权限文件
                continue

            if len(matches) >= limit:
                break

        if not matches:
            return "无匹配结果"
        return "\n".join(matches)

    def _tool_run_command(self, command: str, timeout: int = 300) -> str:
        """执行终端命令：支持交互式检测、更长超时、更好的错误处理"""
        parts = command.split()
        if not parts:
            return "错误：空命令"

        # 交互式命令检测
        interactive_hint = self._check_interactive_command(command)
        if interactive_hint:
            return interactive_hint

        base = parts[0]
        # 白名单检查：支持完整路径中包含白名单命令
        cmd_name = Path(base).name
        if cmd_name not in COMMAND_WHITELIST:
            return f"错误：命令 '{cmd_name}' 不在白名单中，允许的命令：{', '.join(sorted(COMMAND_WHITELIST))}"

        try:
            # 使用 asyncio 运行命令（支持更好的超时控制）
            if sys.platform == "win32":
                # Windows 需要设置事件循环策略
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                output = loop.run_until_complete(self._run_command_async(command, timeout))
                return output
            finally:
                loop.close()

        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（{timeout}秒）。提示：对于长时间运行的命令，可以增加 timeout 参数。"
        except Exception as e:
            return f"错误：命令执行失败 - {e}"

    async def _run_command_async(self, command: str, timeout: int) -> str:
        """异步执行命令（支持更好的超时控制）"""
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.project_dir) if self.project_dir else None,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += f"\n[stderr]\n{stderr.decode('utf-8', errors='replace')}"
            if process.returncode != 0:
                output += f"\n[exit code: {process.returncode}]"

            # 截断过长输出
            if len(output) > 12000:
                output = output[:12000] + "\n...[输出已截断]..."

            return output if output.strip() else "(无输出)"

        except asyncio.TimeoutError:
            # 超时时尝试优雅终止
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            raise subprocess.TimeoutExpired(command, timeout)

    def _check_interactive_command(self, command: str) -> str | None:
        """检测交互式命令，提前拒绝避免卡死"""
        lowered = command.lower()

        # 交互式脚手架命令
        interactive_markers = [
            "npm create ",
            "pnpm create ",
            "yarn create ",
            "bun create ",
            "npm init ",
            "pnpm init ",
            "yarn init ",
            "npx create-",
            "bunx create-",
            "cargo new ",
            "cargo init ",
        ]

        # 非交互式标志
        non_interactive_flags = [
            "--yes",
            " -y",
            "--skip-install",
            "--defaults",
            "--non-interactive",
            "--ci",
        ]

        # 如果是交互式命令且没有非交互式标志
        is_interactive = any(marker in lowered for marker in interactive_markers)
        has_non_interactive_flag = any(flag in lowered for flag in non_interactive_flags)

        if is_interactive and not has_non_interactive_flag:
            return (
                "错误：此命令需要交互式输入，但 run_command 工具不支持交互。\n"
                "建议：添加非交互式标志（如 --yes、-y、--defaults、--non-interactive）。\n"
                f"示例：{command} --yes"
            )

        return None

    def _resolve_safe_path(self, path: str) -> Path:
        base = self.project_dir or Path.cwd()
        target = (base / path).resolve()
        # 防止路径穿越
        if not str(target).startswith(str(base.resolve())):
            raise ValueError(f"路径穿越：{path} 不在项目目录内")
        return target


# ---- 工具定义（Claude tool use 格式） ----

TOOLS_READ_WRITE = [
    {
        "name": "read_file",
        "description": "读取项目中的文件内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对于项目根目录的文件路径"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "创建或修改项目中的文件（完整覆盖）",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对于项目根目录的文件路径"},
                "content": {"type": "string", "description": "要写入的文件内容"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "编辑文件：用 new_string 替换 old_string（diff 模式，节省 token）。优先使用此工具而非 write_file。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对于项目根目录的文件路径"},
                "old_string": {"type": "string", "description": "要替换的原始字符串（必须在文件中存在）"},
                "new_string": {"type": "string", "description": "替换后的新字符串"},
                "replace_all": {
                    "type": "boolean",
                    "description": "是否替换所有匹配项（默认 false，只替换第一个）",
                    "default": False,
                },
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "list_files",
        "description": "列出项目中的文件",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "glob 模式，默认 **/*",
                    "default": "**/*",
                },
            },
        },
    },
    {
        "name": "grep",
        "description": "搜索文件内容：支持正则表达式，优先使用 ripgrep（快速），回退到 Python re",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "正则表达式搜索模式"},
                "file_glob": {
                    "type": "string",
                    "description": "文件过滤 glob 模式，默认 **/*",
                    "default": "**/*",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否区分大小写，默认 true",
                    "default": True,
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回结果数，默认 200",
                    "default": 200,
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "run_command",
        "description": "在项目目录中执行终端命令（仅限白名单命令：python, pip, npm, node, git, pytest, eslint, npx, cargo, go）。支持交互式命令检测。",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 300",
                    "default": 300,
                },
            },
            "required": ["command"],
        },
    },
]

TOOLS_READ_ONLY = [
    tool for tool in TOOLS_READ_WRITE if tool["name"] in {"read_file", "list_files", "grep"}
]
