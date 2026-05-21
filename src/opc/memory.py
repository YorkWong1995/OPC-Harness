"""Memory: 角色记忆系统

参考 MetaGPT 的 Memory 设计，提供：
1. 消息存储和检索
2. 按角色/Action 类型索引
3. 工作记忆和长期记忆的区分
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal, List, Optional, Set, Dict
from .schema import Message

MemoryScope = Literal["user", "project", "workflow", "run", "artifact"]
MemoryWriteAction = Literal["write", "review", "reject", "delete", "supersede"]

SENSITIVE_MEMORY_PATTERNS = [
    "api_key",
    "apikey",
    "anthropic_api_key",
    "secret",
    "password",
    "token=",
    "bearer ",
    "private key",
    "-----begin",
    ".env",
]
EPHEMERAL_MEMORY_MARKERS = ["临时", "temporary", "debug", "调试", "stacktrace", "traceback", "run state"]


@dataclass(frozen=True)
class MemoryWriteDecision:
    action: MemoryWriteAction
    reason: str
    record: "MemoryRecord | None" = None
    audit_event: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRecord:
    content: str
    scope: MemoryScope
    source: str
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    expires_at: str = ""
    superseded_by: str = ""

    def is_expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        current = now or datetime.now(timezone.utc)
        expires = datetime.fromisoformat(self.expires_at)
        return expires <= current

    @property
    def is_long_term(self) -> bool:
        return self.scope in {"user", "project", "workflow"}


LONG_TERM_SCOPES: set[MemoryScope] = {"user", "project", "workflow"}
EPHEMERAL_SCOPES: set[MemoryScope] = {"run", "artifact"}
REQUIRED_MEMORY_FIELDS = {"scope", "created_at", "updated_at", "expires_at", "source", "confidence"}


def requires_write_review(record: MemoryRecord) -> bool:
    return record.scope in LONG_TERM_SCOPES


def can_promote_to_long_term(record: MemoryRecord, confirmed: bool = False) -> bool:
    if record.scope in EPHEMERAL_SCOPES:
        return False
    return confirmed and bool(record.source)


def _memory_audit_event(action: MemoryWriteAction, reason: str, record: MemoryRecord | None = None) -> dict[str, str]:
    event = {"type": "memory_write_policy", "action": action, "reason": reason}
    if record is not None:
        event.update({"scope": record.scope, "source": record.source})
    return event


def detect_sensitive_memory_content(content: str) -> list[str]:
    lowered = content.lower()
    return [pattern for pattern in SENSITIVE_MEMORY_PATTERNS if pattern in lowered]


def evaluate_memory_write(record: MemoryRecord, confirmed: bool = False) -> MemoryWriteDecision:
    matched = detect_sensitive_memory_content(record.content)
    if matched:
        reason = "sensitive_content_rejected"
        return MemoryWriteDecision("reject", reason, audit_event=_memory_audit_event("reject", reason, record))
    lowered = record.content.lower()
    if any(marker in lowered for marker in EPHEMERAL_MEMORY_MARKERS):
        reason = "ephemeral_content_rejected"
        return MemoryWriteDecision("reject", reason, audit_event=_memory_audit_event("reject", reason, record))
    if record.scope in EPHEMERAL_SCOPES:
        reason = "ephemeral_scope_rejected"
        return MemoryWriteDecision("reject", reason, audit_event=_memory_audit_event("reject", reason, record))
    if not record.source:
        reason = "missing_source_rejected"
        return MemoryWriteDecision("reject", reason, audit_event=_memory_audit_event("reject", reason, record))
    if requires_write_review(record) and not confirmed:
        reason = "long_term_memory_requires_confirmation"
        return MemoryWriteDecision("review", reason, record, _memory_audit_event("review", reason, record))
    reason = "memory_write_allowed"
    return MemoryWriteDecision("write", reason, record, _memory_audit_event("write", reason, record))


def write_memory_record(records: list[MemoryRecord], record: MemoryRecord, confirmed: bool = False) -> tuple[list[MemoryRecord], MemoryWriteDecision]:
    decision = evaluate_memory_write(record, confirmed=confirmed)
    if decision.action != "write":
        return records, decision
    return [*records, record], decision


def delete_memory_record(records: list[MemoryRecord], index: int, confirmed: bool = False) -> tuple[list[MemoryRecord], MemoryWriteDecision]:
    if index < 0 or index >= len(records):
        reason = "memory_not_found"
        return records, MemoryWriteDecision("reject", reason, audit_event=_memory_audit_event("reject", reason))
    record = records[index]
    if not confirmed:
        reason = "memory_delete_requires_confirmation"
        return records, MemoryWriteDecision("review", reason, record, _memory_audit_event("review", reason, record))
    reason = "memory_deleted"
    return [*records[:index], *records[index + 1:]], MemoryWriteDecision("delete", reason, record, _memory_audit_event("delete", reason, record))


def supersede_memory_record(
    records: list[MemoryRecord],
    index: int,
    replacement: MemoryRecord,
    confirmed: bool = False,
) -> tuple[list[MemoryRecord], MemoryWriteDecision]:
    if index < 0 or index >= len(records):
        reason = "memory_not_found"
        return records, MemoryWriteDecision("reject", reason, audit_event=_memory_audit_event("reject", reason))
    write_decision = evaluate_memory_write(replacement, confirmed=confirmed)
    if write_decision.action != "write":
        return records, write_decision
    memory_id = f"memory:{len(records)}"
    updated = [*records]
    updated[index] = replace(records[index], superseded_by=memory_id, updated_at=datetime.now(timezone.utc).isoformat())
    updated.append(replacement)
    reason = "memory_superseded"
    return updated, MemoryWriteDecision("supersede", reason, replacement, _memory_audit_event("supersede", reason, replacement))


def select_memory_for_context(
    records: list[MemoryRecord],
    role: str,
    allowed_scopes: set[MemoryScope] | None = None,
    current_facts: set[str] | None = None,
) -> tuple[list[MemoryRecord], list[dict[str, str]]]:
    scopes = allowed_scopes or LONG_TERM_SCOPES
    facts = current_facts or set()
    selected: list[MemoryRecord] = []
    sources: list[dict[str, str]] = []
    for index, record in enumerate(records):
        memory_id = f"memory:{index}"
        if record.scope not in scopes:
            continue
        if record.is_expired():
            sources.append({
                "type": "memory",
                "name": memory_id,
                "scope": record.scope,
                "source": record.source,
                "status": "expired",
                "reason": "expired",
            })
            continue
        if record.content in facts:
            sources.append({
                "type": "memory",
                "name": memory_id,
                "scope": record.scope,
                "source": record.source,
                "status": "conflict_current_fact",
                "reason": "current_fact_preferred",
            })
            continue
        selected.append(record)
        sources.append({
            "type": "memory",
            "name": memory_id,
            "scope": record.scope,
            "source": record.source,
            "role": role,
            "status": "selected",
            "reason": "scope_role_match",
        })
    return selected, sources


class Memory:
    """记忆系统：存储和检索消息历史

    核心功能：
    1. 存储所有消息
    2. 按角色、Action 类型、时间等维度检索
    3. 支持工作记忆（当前任务相关）和长期记忆（全部历史）
    """

    def __init__(self):
        self.storage: List[Message] = []  # 所有消息
        self._index_by_role: Dict[str, List[Message]] = {}  # 按角色索引
        self._index_by_action: Dict[str, List[Message]] = {}  # 按 Action 索引

    def add(self, message: Message):
        """添加消息到记忆"""
        self.storage.append(message)

        # 更新角色索引
        if message.role not in self._index_by_role:
            self._index_by_role[message.role] = []
        self._index_by_role[message.role].append(message)

        # 更新 Action 索引
        if message.cause_by:
            if message.cause_by not in self._index_by_action:
                self._index_by_action[message.cause_by] = []
            self._index_by_action[message.cause_by].append(message)

    def get(self, limit: Optional[int] = None) -> List[Message]:
        """获取所有消息

        Args:
            limit: 最多返回多少条消息（最新的）

        Returns:
            消息列表
        """
        if limit:
            return self.storage[-limit:]
        return self.storage.copy()

    def get_by_role(self, role: str, limit: Optional[int] = None) -> List[Message]:
        """按角色检索消息

        Args:
            role: 角色名
            limit: 最多返回多少条消息

        Returns:
            该角色的消息列表
        """
        messages = self._index_by_role.get(role, [])
        if limit:
            return messages[-limit:]
        return messages.copy()

    def get_by_actions(self, actions: Set[str], limit: Optional[int] = None) -> List[Message]:
        """按 Action 类型检索消息

        Args:
            actions: Action 类型集合
            limit: 最多返回多少条消息

        Returns:
            匹配的消息列表
        """
        result = []
        for action in actions:
            if action in self._index_by_action:
                result.extend(self._index_by_action[action])

        # 按时间排序
        result.sort(key=lambda msg: msg.timestamp)

        if limit:
            return result[-limit:]
        return result

    def get_recent(self, n: int = 10) -> List[Message]:
        """获取最近的 n 条消息"""
        return self.storage[-n:]

    def search(self, keyword: str, limit: int = 10) -> List[Message]:
        """搜索包含关键词的消息

        Args:
            keyword: 搜索关键词
            limit: 最多返回多少条消息

        Returns:
            包含关键词的消息列表
        """
        result = []
        keyword_lower = keyword.lower()

        for msg in reversed(self.storage):  # 从最新的开始搜索
            if keyword_lower in msg.content.lower():
                result.append(msg)
                if len(result) >= limit:
                    break

        return result

    def clear(self):
        """清空所有记忆"""
        self.storage.clear()
        self._index_by_role.clear()
        self._index_by_action.clear()

    def __len__(self) -> int:
        return len(self.storage)

    def __repr__(self) -> str:
        return f"Memory(messages={len(self.storage)}, roles={len(self._index_by_role)})"


class WorkingMemory(Memory):
    """工作记忆：当前任务相关的短期记忆

    特点：
    1. 容量有限（默认最多保留 50 条消息）
    2. 自动清理旧消息
    3. 用于当前任务的上下文
    """

    def __init__(self, max_size: int = 50):
        super().__init__()
        self.max_size = max_size

    def add(self, message: Message):
        """添加消息，超过容量时自动清理最旧的"""
        super().add(message)

        # 超过容量时，移除最旧的消息
        if len(self.storage) > self.max_size:
            # 移除最旧的消息
            old_msg = self.storage.pop(0)

            # 更新索引
            if old_msg.role in self._index_by_role:
                self._index_by_role[old_msg.role].remove(old_msg)

            if old_msg.cause_by and old_msg.cause_by in self._index_by_action:
                self._index_by_action[old_msg.cause_by].remove(old_msg)

    def is_full(self) -> bool:
        """检查工作记忆是否已满"""
        return len(self.storage) >= self.max_size
