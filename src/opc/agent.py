"""Agent 基类：封装 Claude API 调用与 tool use 循环"""

from __future__ import annotations

import asyncio
from pathlib import Path
import os
import time

import anthropic

from .rag import SimpleRAG, create_rag_for_project
from .schema import Message, MessageQueue
from .security.path_validator import check_workspace_boundary, resolve_safe_path
from .tools.build_tools import BuildToolsMixin
from .tools.command_tools import CommandToolsMixin
from .tools.file_tools import FileToolsMixin
from .tools.git_tools import GitToolsMixin
from .tools.knowledge_tools import KnowledgeToolsMixin
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


class Agent(FileToolsMixin, KnowledgeToolsMixin, GitToolsMixin, BuildToolsMixin, CommandToolsMixin):
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
                        summary = self._summarize_tool_result(block.name, result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": summary["content"],
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

    @staticmethod
    def _summarize_tool_result(name: str, result: str | None, limit: int = 500) -> dict:
        content = "" if result is None else str(result)
        truncated = len(content) > limit
        preview = content[:limit]
        if truncated:
            preview = f"[tool_result_summary tool={name} original_chars={len(content)} truncated=true]\n{preview}"
        return {
            "content": preview,
            "preview": content[:limit],
            "truncated": truncated,
            "original_chars": len(content),
        }

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
        summary = self._summarize_tool_result(name, result)
        record = {
            "tool_name": name,
            "inputs": inputs,
            "result": summary["preview"] if result else None,
            "result_truncated": summary["truncated"],
            "result_original_chars": summary["original_chars"],
            "elapsed": round(elapsed, 3),
            "tool_use_id": tool_use_id,
            "error": error,
        }
        # 将记录添加到审计日志（后续可由 workflow 写入 RunStore）
        self.audit_log.append(record)

    def _check_workspace_boundary(self, args: list[str]) -> str | None:
        return check_workspace_boundary(self.project_dir, args)

    def _resolve_safe_path(self, path: str) -> Path:
        return resolve_safe_path(self.project_dir, path)


# ---- 工具定义（Claude tool use 格式） ----

TOOLS_READ_WRITE = list_tool_schemas()

TOOLS_READ_ONLY = list_tool_schemas(permissions={"read"})
