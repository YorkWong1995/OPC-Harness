"""OPC 核心数据结构定义"""

from datetime import datetime
import json
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


VALID_ROLES = {"ceo", "pm", "architect", "engineer", "qa", "ops", "growth", "system", "all"}
VALID_CAUSES = {
    "user_request",
    "growth_research",
    "prd_definition",
    "architecture_design",
    "implementation",
    "qa_review",
    "ops_check",
    "retrospective",
    "tool_result",
    "workflow_event",
}


class Message(BaseModel):
    """消息：角色间通信的基本单位

    参考 MetaGPT 的 Message 设计，但简化版本。
    """

    content: str = Field(description="消息内容")
    role: str = Field(description="发送者角色（pm, engineer, qa, etc.）")
    cause_by: Optional[str] = Field(default=None, description="由哪个 Action 产生")
    send_to: Optional[str] = Field(default=None, description="发送给谁（角色名或 'all'）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间")

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:100]}..."

    def is_sent_to(self, role: str) -> bool:
        """判断消息是否发送给指定角色"""
        if self.send_to is None or self.send_to == "all":
            return True
        return self.send_to == role

    def validate_route(self, known_roles: set[str] | None = None) -> None:
        roles = known_roles or VALID_ROLES
        if self.send_to is not None and self.send_to not in roles:
            allowed = ", ".join(sorted(roles))
            raise ValueError(f"非法 send_to: {self.send_to}。允许值：{allowed}")
        if self.cause_by is not None and self.cause_by not in VALID_CAUSES:
            allowed = ", ".join(sorted(VALID_CAUSES))
            raise ValueError(f"非法 cause_by: {self.cause_by}。允许值：{allowed}")


class MessageQueue:
    """消息队列：存储待处理的消息"""

    def __init__(self):
        self._queue: list[Message] = []

    def push(self, message: Message):
        """添加消息到队列"""
        self._queue.append(message)

    def pop(self) -> Optional[Message]:
        """取出一条消息"""
        if self._queue:
            return self._queue.pop(0)
        return None

    def pop_all(self) -> list[Message]:
        """取出所有消息"""
        messages = self._queue.copy()
        self._queue.clear()
        return messages

    def peek(self) -> Optional[Message]:
        """查看队首消息但不移除"""
        if self._queue:
            return self._queue[0]
        return None

    def __len__(self) -> int:
        return len(self._queue)

    def __bool__(self) -> bool:
        return len(self._queue) > 0


class PMOutput(BaseModel):
    background: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    scope: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class EngineerOutput(BaseModel):
    changed_files: list[str] = Field(default_factory=list)
    implementation_summary: str = Field(min_length=1)
    test_result: str = ""
    known_limits: list[str] = Field(default_factory=list)
    failure_reason: str = ""
    blocked_by: list[str] = Field(default_factory=list)
    suggested_next_step: str = ""


class QAOutput(BaseModel):
    status: Literal["pass", "fail"]
    checked_items: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    defects: list[str] = Field(default_factory=list)
    next_action: Literal["done", "rework", "human_intervention"] = "done"


class StageSummary(BaseModel):
    stage: str = Field(min_length=1)
    goal: str = ""
    decisions: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    validation: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_step: str = ""


ROLE_OUTPUT_SCHEMAS = {
    "pm": PMOutput,
    "engineer": EngineerOutput,
    "qa": QAOutput,
}


def parse_role_output(role: str, content: str) -> BaseModel:
    schema = ROLE_OUTPUT_SCHEMAS[role]
    data = _extract_json_object(content)
    return schema.model_validate(data)


def _extract_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("角色输出不是 JSON 对象")
        stripped = stripped[start : end + 1]
    data, _ = json.JSONDecoder().raw_decode(stripped)
    if not isinstance(data, dict):
        raise ValueError("角色输出必须是 JSON 对象")
    return data
