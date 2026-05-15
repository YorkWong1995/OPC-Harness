"""Agent 基类：封装 Claude API 调用与 tool use 循环"""

from __future__ import annotations

import subprocess
from pathlib import Path
import re
import shutil
import asyncio
import sys

import os

import time

import anthropic

from .rag import SimpleRAG, create_rag_for_project
from .schema import Message, MessageQueue
from .tools.tool_registry import get_tool, list_tool_schemas, load_plugin_tools

# 重试配置：遇到上游波动时等待并重试
RETRY_MAX_ATTEMPTS = int(os.environ.get("OPC_RETRY_MAX", "3"))
# 区分交互模式（CLI/IDE 实时使用）与批处理模式（夜间任务）
# 默认使用交互模式 10s，避免一次重试就让用户等 30 分钟
RETRY_BASE_DELAYS = {
    "interactive": int(os.environ.get("OPC_RETRY_INTERACTIVE_DELAY", "10")),
    "batch": int(os.environ.get("OPC_RETRY_BATCH_DELAY", "1800")),
}
RETRY_DEFAULT_MODE = os.environ.get("OPC_RETRY_MODE", "interactive")
# 兼容历史变量：保留 OPC_RETRY_BASE_DELAY 以覆盖批处理延迟
if os.environ.get("OPC_RETRY_BASE_DELAY"):
    RETRY_BASE_DELAYS["batch"] = int(os.environ["OPC_RETRY_BASE_DELAY"])
RETRY_BASE_DELAY = RETRY_BASE_DELAYS.get(RETRY_DEFAULT_MODE, RETRY_BASE_DELAYS["interactive"])

# 可重试的 HTTP 状态码（上游波动、过载）
RETRYABLE_STATUS_CODES = {500, 502, 503, 529}

# 允许 run_command 执行的命令白名单
COMMAND_WHITELIST = {
    "python", "pip", "npm", "node", "git", "pytest", "eslint", "npx", "cargo", "go",
    "gcc", "g++", "cmake", "make", "cl", "clang", "clang++", "nmake", "msbuild"
}

# 危险参数模式：命令 -> 需要审计的参数关键词
DANGEROUS_PARAMS: dict[str, list[str]] = {
    "git": ["push --force", "reset --hard", "clean -f", "branch -D"],
    "pip": ["install --pre", "install --force-reinstall"],
    "npm": ["publish", "unpublish"],
    "rm": ["-rf", "-r"],
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
        tool_max_retries: int = 1,
        max_tool_rounds: int | None = None,
        run_store: "RunStore | None" = None,
        retry_mode: str | None = None,
    ):
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools
        self.project_dir = project_dir
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        self.enable_rag = enable_rag
        self.rag: SimpleRAG | None = None
        self.tool_max_retries = tool_max_retries
        # 工具循环上限：防止 Agent 失控烧 token；可通过环境变量覆盖
        if max_tool_rounds is None:
            max_tool_rounds = int(os.environ.get("OPC_MAX_TOOL_ROUNDS", "15"))
        self.max_tool_rounds = max_tool_rounds
        self.run_store = run_store
        # 重试模式：interactive (10s) / batch (1800s)；默认 interactive
        mode = retry_mode or os.environ.get("OPC_RETRY_MODE", "interactive")
        self.retry_mode = mode if mode in RETRY_BASE_DELAYS else "interactive"
        self.retry_base_delay = RETRY_BASE_DELAYS[self.retry_mode]

        # 消息缓冲区（用于 Environment 集成）
        self.msg_buffer = MessageQueue()

        # 审计日志：记录危险命令和工具调用事件
        self.audit_log: list[dict] = []

        # 上一次 run() 累计的 token 用量（跨多轮 tool use 调用累加）
        self.last_input_tokens = 0
        self.last_output_tokens = 0
        self.last_tool_calls = 0
        self.last_api_calls = 0

        # 初始化 RAG
        if enable_rag and project_dir:
            self.rag = create_rag_for_project(project_dir)

        load_plugin_tools(project_dir)

        # 支持中转地址：若设置了 ANTHROPIC_BASE_URL 则使用自定义端点
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        self.client = anthropic.Anthropic(
            base_url=base_url if base_url else None,
        )

    def _is_retryable(self, error: Exception) -> bool:
        """判断错误是否可重试（上游波动、过载等）"""
        if isinstance(error, anthropic.APITimeoutError):
            return True
        if isinstance(error, anthropic.APIError):
            status = getattr(error, "status_code", None)
            return status in RETRYABLE_STATUS_CODES
        return False

    def _call_with_retry(self, **kwargs) -> anthropic.types.Message:
        """带指数退避重试的 API 调用，基础间隔由 retry_mode 决定"""
        last_error = None
        for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
            try:
                return self.client.messages.create(**kwargs)
            except Exception as e:
                last_error = e
                if not self._is_retryable(e):
                    raise
                if attempt < RETRY_MAX_ATTEMPTS:
                    delay = self.retry_base_delay * (2 ** (attempt - 1))
                    minutes = delay // 60
                    pretty = f"{minutes} 分钟" if minutes > 0 else f"{delay} 秒"
                    print(
                        f"[{self.role}] 上游服务暂时不可用 "
                        f"(第 {attempt}/{RETRY_MAX_ATTEMPTS} 次, mode={self.retry_mode})，"
                        f"{pretty}后重试... 错误: {e}"
                    )
                    time.sleep(delay)
        raise last_error

    def receive(self, message: Message):
        """接收消息（用于 Environment 集成）"""
        self.msg_buffer.push(message)

    def has_pending_messages(self) -> bool:
        """检查是否有待处理的消息"""
        return bool(self.msg_buffer)

    async def observe_think_act(self, stop_event: asyncio.Event | None = None) -> list[str]:
        """持续处理消息缓冲区，直到空闲或收到停止信号。"""
        results: list[str] = []
        while self.has_pending_messages():
            if stop_event and stop_event.is_set():
                break
            messages = self.msg_buffer.pop_all()
            prompt = "\n\n".join(f"[{msg.role}] {msg.content}" for msg in messages)
            result = await asyncio.to_thread(self.run, prompt)
            results.append(result)
        return results

    def run(self, message: str) -> str:
        # 重置本次 run 的 token 计数
        self.last_input_tokens = 0
        self.last_output_tokens = 0
        self.last_tool_calls = 0
        self.last_api_calls = 0

        # 如果启用 RAG，先检索相关文档
        if self.rag:
            context = self.rag.get_context(message, max_tokens=2000)
            if context and context != "未找到相关文档。":
                print(f"[RAG][{self.role}] 检索到相关文档，添加到上下文")
                message = f"{message}\n\n---\n\n{context}"

        messages = [{"role": "user", "content": message}]

        tool_rounds = 0
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
                self.last_api_calls += 1
                response = self._call_with_retry(**kwargs)
            except anthropic.APITimeoutError as e:
                error_msg = f"[{self.role}] API 调用超时（已重试 {RETRY_MAX_ATTEMPTS} 次）: {e}"
                print(error_msg)
                return error_msg
            except anthropic.APIError as e:
                error_msg = f"[{self.role}] API 调用错误（不可重试）: {e}"
                print(error_msg)
                return error_msg
            except Exception as e:
                error_msg = f"[{self.role}] 未知错误: {e}"
                print(error_msg)
                return error_msg

            # 从 response.usage 提取 token 计数（多轮 tool use 时累加）
            usage = getattr(response, "usage", None)
            if usage is not None:
                self.last_input_tokens += getattr(usage, "input_tokens", 0) or 0
                self.last_output_tokens += getattr(usage, "output_tokens", 0) or 0

            # 收集响应中的内容块
            stop_reason = response.stop_reason
            assistant_content = response.content

            if stop_reason == "end_turn":
                return self._extract_text(assistant_content)

            if stop_reason == "tool_use":
                tool_rounds += 1
                if tool_rounds > self.max_tool_rounds:
                    truncated_msg = (
                        f"[TRUNCATED] 工具调用轮次已超过上限 {self.max_tool_rounds}，"
                        f"中止以避免失控；可通过 max_tool_rounds 或 OPC_MAX_TOOL_ROUNDS 调整。"
                    )
                    print(f"[WARN][{self.role}] {truncated_msg}")
                    if self.run_store is not None:
                        try:
                            self.run_store.append(
                                "tool_rounds_truncated",
                                role=self.role,
                                max_tool_rounds=self.max_tool_rounds,
                            )
                        except Exception:
                            pass
                    existing = self._extract_text(assistant_content)
                    return f"{existing}\n{truncated_msg}" if existing else truncated_msg

                # 把 assistant 回复加入消息历史
                messages.append({"role": "assistant", "content": assistant_content})

                # 处理所有 tool_use 调用，收集结果
                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        self.last_tool_calls += 1
                        result = self._execute_tool(block.name, block.input, tool_use_id=block.id)
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

    def _execute_tool(self, name: str, inputs: dict, tool_use_id: str | None = None) -> str:
        definition = get_tool(name)
        if not definition:
            return f"错误：未知工具 {name}"
        if definition.handler_name:
            handler = getattr(self, definition.handler_name)
        else:
            handler = definition.handler

        # 日志：工具调用开始
        print(f"[DEBUG][{self.role}] 执行工具: {name}")
        if name == "read_file":
            print(f"  -> 文件: {inputs.get('file_path', 'N/A')}")
        elif name == "write_file":
            print(f"  -> 文件: {inputs.get('file_path', 'N/A')}")
        elif name == "grep":
            print(f"  -> 模式: {inputs.get('pattern', 'N/A')}")
        elif name == "search_knowledge":
            print(f"  -> 查询: {inputs.get('query', 'N/A')}")
        elif name in {"git_status", "git_diff", "git_log"}:
            print(f"  -> Git 工具: {name}")
        elif name == "run_tests":
            print(f"  -> 测试目标: {inputs.get('target', 'all')}")
        elif name in {"run_lint", "run_typecheck", "run_build"}:
            print(f"  -> 验证工具: {name}")
        elif name == "run_command":
            print(f"  -> 命令: {inputs.get('command', 'N/A')}")

        start_time = time.time()
        last_error = None
        max_attempts = self.tool_max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                result = handler(**inputs)
                elapsed = time.time() - start_time
                result_preview = str(result)[:200] if result else "None"
                print(f"[DEBUG][{self.role}] 工具执行成功，结果预览: {result_preview}...")
                self._record_tool_call(name, inputs, result, elapsed, tool_use_id, error=None)
                return result
            except Exception as e:
                last_error = e
                is_retryable = self._is_tool_retryable(e)
                if is_retryable and attempt < max_attempts:
                    print(f"[WARN][{self.role}] 工具 {name} 第 {attempt} 次失败（可重试）: {e}")
                    time.sleep(min(2 ** attempt, 10))
                    continue
                break

        elapsed = time.time() - start_time
        error_msg = f"工具执行错误：{last_error}"
        print(f"[ERROR][{self.role}] {error_msg}")
        self._record_tool_call(name, inputs, None, elapsed, tool_use_id, error=str(last_error))
        return error_msg

    @staticmethod
    def _is_tool_retryable(error: Exception) -> bool:
        """判断工具执行错误是否可重试"""
        error_str = str(error).lower()
        non_retryable = ("不存在", "not found", "permission denied", "不允许", "未找到", "是目录")
        return not any(keyword in error_str for keyword in non_retryable)

    def _record_tool_call(self, name: str, inputs: dict, result: str | None, elapsed: float,
                          tool_use_id: str | None, error: str | None):
        """记录工具调用和结果（供 RunStore 持久化）"""
        record = {
            "tool_name": name,
            "inputs": inputs,
            "result": result[:500] if result else None,  # 限制结果长度
            "elapsed": round(elapsed, 3),
            "tool_use_id": tool_use_id,
            "error": error,
        }
        # 将记录添加到审计日志（后续可由 workflow 写入 RunStore）
        self.audit_log.append(record)

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

    def _tool_search_knowledge(self, query: str, top_k: int = 5, index_name: str | None = None) -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"

        from .knowledge.bm25_index import BM25Index
        from .knowledge.indexer import Indexer
        from .knowledge.retriever import Retriever
        from .knowledge.vector_store import VectorStore

        name = index_name or self.project_dir.name
        index_root = self.project_dir / "index"
        meta = Indexer.load_meta(index_root)
        if meta is None:
            return f"错误：知识索引不存在，请先运行 opc index --name {name} --dirs {self.project_dir}"

        bm25 = BM25Index()
        bm25.load(index_root / "bm25")
        vector_store = VectorStore(index_root / "chroma")
        vector_store.create_collection(meta.index_name)
        retriever = Retriever(vector_store, bm25)
        results = retriever.retrieve(query, top_k=top_k)
        if not results:
            return "未找到相关知识。"

        lines = []
        for i, result in enumerate(results, 1):
            chunk = result.chunk
            preview = chunk.content[:800]
            if len(chunk.content) > 800:
                preview += "\n..."
            lines.append(
                f"[{i}] {chunk.file_path}:{chunk.start_line}-{chunk.end_line} "
                f"score={result.rrf_score:.4f}\n{preview}"
            )
        return "\n\n".join(lines)

    def _tool_git_status(self, porcelain: bool = True) -> str:
        args = ["status", "--short"] if porcelain else ["status"]
        return self._run_git(args)

    def _tool_git_diff(self, cached: bool = False, path: str | None = None) -> str:
        args = ["diff"]
        if cached:
            args.append("--cached")
        if path:
            target = self._resolve_safe_path(path)
            args.extend(["--", str(target.relative_to((self.project_dir or Path.cwd()).resolve()))])
        return self._run_git(args)

    def _tool_git_log(self, limit: int = 5) -> str:
        bounded_limit = max(1, min(int(limit), 50))
        return self._run_git(["log", "--oneline", "-n", str(bounded_limit)])

    def _run_git(self, args: list[str]) -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output = f"{output}\n[stderr]\n{result.stderr.strip()}" if output else f"[stderr]\n{result.stderr.strip()}"
        if result.returncode != 0:
            output = f"{output}\n[exit code: {result.returncode}]" if output else f"[exit code: {result.returncode}]"
        return output or "(无输出)"

    def _tool_run_lint(self, target: str | None = None, timeout: int = 120) -> str:
        return self._run_project_tool(
            self._detect_lint_command(target), timeout, "lint"
        )

    def _tool_run_typecheck(self, target: str | None = None, timeout: int = 120) -> str:
        return self._run_project_tool(
            self._detect_typecheck_command(target), timeout, "typecheck"
        )

    def _tool_run_build(self, timeout: int = 300) -> str:
        return self._run_project_tool(
            self._detect_build_command(), timeout, "build"
        )

    def _detect_lint_command(self, target: str | None = None) -> list[str] | None:
        if not self.project_dir:
            return None
        resolved_target = str(self._resolve_safe_path(target).relative_to(self.project_dir.resolve())) if target else "."
        if (self.project_dir / "pyproject.toml").exists() or (self.project_dir / "setup.py").exists():
            return [sys.executable, "-m", "ruff", "check", resolved_target]
        if (self.project_dir / "package.json").exists():
            return ["npx", "eslint", resolved_target]
        return None

    def _detect_typecheck_command(self, target: str | None = None) -> list[str] | None:
        if not self.project_dir:
            return None
        resolved_target = str(self._resolve_safe_path(target).relative_to(self.project_dir.resolve())) if target else "."
        if (self.project_dir / "pyproject.toml").exists() or (self.project_dir / "setup.py").exists():
            return [sys.executable, "-m", "mypy", resolved_target]
        if (self.project_dir / "tsconfig.json").exists():
            return ["npx", "tsc", "--noEmit"]
        return None

    def _detect_build_command(self) -> list[str] | None:
        if not self.project_dir:
            return None
        if (self.project_dir / "pyproject.toml").exists() or (self.project_dir / "setup.py").exists():
            return [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"]
        if (self.project_dir / "package.json").exists():
            return ["npm", "run", "build"]
        if (self.project_dir / "Cargo.toml").exists():
            return ["cargo", "build"]
        return None

    def _run_project_tool(self, command: list[str] | None, timeout: int, label: str) -> str:
        if command is None:
            return f"错误：未检测到可用的 {label} 命令，请确认项目配置"
        bounded_timeout = max(1, min(int(timeout), 1800))
        try:
            result = subprocess.run(
                command,
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=bounded_timeout,
            )
        except subprocess.TimeoutExpired:
            return f"错误：{label} 执行超时（{bounded_timeout}秒）"
        except FileNotFoundError:
            return f"错误：{label} 工具未安装（{command[0]}）"
        output = result.stdout.strip()
        if result.stderr.strip():
            output = f"{output}\n[stderr]\n{result.stderr.strip()}" if output else f"[stderr]\n{result.stderr.strip()}"
        if result.returncode != 0:
            output = f"{output}\n[exit code: {result.returncode}]" if output else f"[exit code: {result.returncode}]"
        if len(output) > 12000:
            output = output[:12000] + "\n...[输出已截断]..."
        return output or "(无输出)"

    def _tool_run_tests(self, target: str | None = None, timeout: int = 300, quiet: bool = True) -> str:
        if not self.project_dir:
            return "错误：未设置项目目录"
        command = [sys.executable, "-m", "pytest"]
        if quiet:
            command.append("-q")
        if target:
            resolved_target = self._resolve_safe_path(target)
            command.append(str(resolved_target.relative_to(self.project_dir.resolve())))
        bounded_timeout = max(1, min(int(timeout), 1800))
        result = subprocess.run(
            command,
            cwd=str(self.project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=bounded_timeout,
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output = f"{output}\n[stderr]\n{result.stderr.strip()}" if output else f"[stderr]\n{result.stderr.strip()}"
        if result.returncode != 0:
            output = f"{output}\n[exit code: {result.returncode}]" if output else f"[exit code: {result.returncode}]"
        if len(output) > 12000:
            output = output[:12000] + "\n...[输出已截断]..."
        return output or "(无输出)"

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

        # 危险参数检测（轻限制：仅记录警告，不阻断执行）
        danger_warning = self._check_dangerous_params(cmd_name, command)

        # 工作目录边界检查：拒绝引用 workspace 外绝对路径的命令
        workspace_violation = self._check_workspace_boundary(parts[1:])
        if workspace_violation:
            return workspace_violation

        try:
            # 使用 asyncio 运行命令（支持更好的超时控制）
            if sys.platform == "win32":
                # Windows 需要设置事件循环策略
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                output = loop.run_until_complete(self._run_command_async(command, timeout))
                if danger_warning:
                    output = f"[WARNING] {danger_warning}\n{output}"
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

    def _check_dangerous_params(self, cmd_name: str, full_command: str) -> str | None:
        patterns = DANGEROUS_PARAMS.get(cmd_name, [])
        lowered = full_command.lower()
        matched = [p for p in patterns if p in lowered]
        if matched:
            warning = f"检测到危险参数: {', '.join(matched)}"
            print(f"[AUDIT][{self.role}] {warning} | 命令: {full_command}")
            self.audit_log.append({
                "event": "dangerous_command",
                "role": self.role,
                "command": full_command,
                "matched_patterns": matched,
            })
            return warning
        return None

    def _check_workspace_boundary(self, args: list[str]) -> str | None:
        if not self.project_dir:
            return None
        workspace = self.project_dir.resolve()
        for arg in args:
            if arg.startswith("-"):
                continue
            candidate = Path(arg)
            if candidate.is_absolute():
                try:
                    resolved = candidate.resolve()
                    if not resolved.is_relative_to(workspace):
                        return f"错误：命令参数引用了 workspace 外的路径: {arg}"
                except (OSError, ValueError):
                    pass
        return None

    def _resolve_safe_path(self, path: str) -> Path:
        base = self.project_dir or Path.cwd()
        target = (base / path).resolve()
        # 防止路径穿越：使用 is_relative_to（Python 3.9+），避免 startswith 前缀误匹配
        # 例如：/home/user/projectX 不能因为 startswith /home/user/proj 而被放行
        try:
            if not target.is_relative_to(base.resolve()):
                raise ValueError(f"路径穿越：{path} 不在项目目录内")
        except AttributeError:
            # Python < 3.9 兜底（项目要求 3.9+，理论上不会进入）
            base_resolved = base.resolve()
            try:
                target.relative_to(base_resolved)
            except ValueError:
                raise ValueError(f"路径穿越：{path} 不在项目目录内")
        return target


# ---- 工具定义（Claude tool use 格式） ----

TOOLS_READ_WRITE = list_tool_schemas()

TOOLS_READ_ONLY = list_tool_schemas(permissions={"read"})
