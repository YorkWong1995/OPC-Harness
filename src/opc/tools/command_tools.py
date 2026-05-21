"""Generic command execution tool implementation for Agent."""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import sys

from ..security.command_whitelist import COMMAND_WHITELIST, check_interactive_command, match_dangerous_params
from ..tools.tool_registry import get_tool


class CommandToolsMixin:
    def _tool_run_command(self, command: str, timeout: int = 300) -> str:
        parts = command.split()
        if not parts:
            return "错误：空命令"

        interactive_hint = self._check_interactive_command(command)
        if interactive_hint:
            return interactive_hint

        cmd_name = Path(parts[0]).name
        if cmd_name not in COMMAND_WHITELIST:
            return f"错误：命令 '{cmd_name}' 不在白名单中，允许的命令：{', '.join(sorted(COMMAND_WHITELIST))}"

        guardrail_message = self._check_command_guardrail(command)
        if guardrail_message and guardrail_message.startswith("["):
            return guardrail_message
        danger_decision = self._check_dangerous_params(cmd_name, command)
        if danger_decision and danger_decision.startswith("["):
            return danger_decision
        workspace_violation = self._check_workspace_boundary(parts[1:])
        if workspace_violation:
            return workspace_violation

        try:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                output = loop.run_until_complete(self._run_command_async(command, timeout))
                if danger_decision:
                    output = f"[WARNING] {danger_decision}\n{output}"
                return output
            finally:
                loop.close()
        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（{timeout}秒）。提示：对于长时间运行的命令，可以增加 timeout 参数。"
        except Exception as error:
            return f"错误：命令执行失败 - {error}"

    async def _run_command_async(self, command: str, timeout: int) -> str:
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
            if len(output) > 12000:
                output = output[:12000] + "\n...[输出已截断]..."
            return output if output.strip() else "(无输出)"
        except asyncio.TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            raise subprocess.TimeoutExpired(command, timeout)

    def _check_interactive_command(self, command: str) -> str | None:
        return check_interactive_command(command)

    def _check_command_guardrail(self, command: str) -> str | None:
        policy = getattr(self, "guardrail_policy", None)
        definition = get_tool("run_command")
        if policy is None or definition is None:
            return None
        decision = policy.check_tool(definition, {"command": command})
        if decision.allowed:
            if decision.action == "audit":
                self.audit_log.append({
                    "event": "guardrail_warning",
                    "role": self.role,
                    "command": command,
                    "matched_patterns": decision.matched_patterns,
                    "reason": decision.reason,
                })
                return decision.reason
            return None
        event_name = "approval_required" if decision.action == "approval" else "guardrail_stopped" if decision.action == "stop" else "guardrail_blocked"
        self.audit_log.append({
            "event": event_name,
            "role": self.role,
            "command": command,
            "matched_patterns": decision.matched_patterns,
            "reason": decision.reason,
        })
        if getattr(self, "run_store", None) is not None:
            self.run_store.append(
                event_name,
                role=self.role,
                tool_name="run_command",
                reason=decision.reason,
                matched_patterns=decision.matched_patterns,
            )
        message = f"[{event_name}] {decision.reason}"
        if decision.matched_patterns:
            message += f": {', '.join(decision.matched_patterns)}"
        return message

    def _check_dangerous_params(self, cmd_name: str, full_command: str) -> str | None:
        matched = match_dangerous_params(cmd_name, full_command)
        if not matched:
            return None
        policy = getattr(self, "guardrail_policy", None)
        if policy is not None:
            action = policy.dangerous_command_policy
            event_name = "guardrail_warning" if action == "audit" else "approval_required" if action == "approval" else "guardrail_blocked"
            reason = "dangerous command audited" if action == "audit" else "dangerous command requires approval" if action == "approval" else "dangerous command denied"
            self.audit_log.append({
                "event": event_name,
                "role": self.role,
                "command": full_command,
                "matched_patterns": matched,
                "reason": reason,
            })
            if action != "audit":
                return f"[{event_name}] {reason}: {', '.join(matched)}"
        warning = f"检测到危险参数: {', '.join(matched)}"
        print(f"[AUDIT][{self.role}] {warning} | 命令: {full_command}")
        return warning
