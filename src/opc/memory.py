"""Memory: 角色记忆系统

参考 MetaGPT 的 Memory 设计，提供：
1. 消息存储和检索
2. 按角色/Action 类型索引
3. 工作记忆和长期记忆的区分
"""

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal, List, Optional, Set, Dict
from uuid import uuid4

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
    id: str = field(default_factory=lambda: _memory_id())
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
REQUIRED_MEMORY_FIELDS = {"id", "scope", "created_at", "updated_at", "expires_at", "source", "confidence"}


def _memory_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_id() -> str:
    return f"memory:{uuid4().hex}"


def _memory_record_to_dict(record: MemoryRecord) -> dict[str, object]:
    return asdict(record)


def _memory_record_from_dict(data: dict[str, object]) -> MemoryRecord:
    values = dict(data)
    values.setdefault("id", _memory_id())
    values.setdefault("confidence", 1.0)
    values.setdefault("created_at", _memory_timestamp())
    values.setdefault("updated_at", "")
    values.setdefault("expires_at", "")
    values.setdefault("superseded_by", "")
    return MemoryRecord(
        id=str(values["id"]),
        content=str(values.get("content", "")),
        scope=values.get("scope", "project"),
        source=str(values.get("source", "")),
        confidence=float(values.get("confidence", 1.0)),
        created_at=str(values.get("created_at", _memory_timestamp())),
        updated_at=str(values.get("updated_at", "")),
        expires_at=str(values.get("expires_at", "")),
        superseded_by=str(values.get("superseded_by", "")),
    )


def requires_write_review(record: MemoryRecord) -> bool:
    return record.scope in LONG_TERM_SCOPES


def can_promote_to_long_term(record: MemoryRecord, confirmed: bool = False) -> bool:
    if record.scope in EPHEMERAL_SCOPES:
        return False
    return confirmed and bool(record.source)


def _memory_audit_event(action: MemoryWriteAction, reason: str, record: MemoryRecord | None = None) -> dict[str, str]:
    event = {"type": "memory_write_policy", "action": action, "reason": reason}
    if record is not None:
        event.update({"id": record.id, "scope": record.scope, "source": record.source})
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
    updated = [*records]
    updated[index] = replace(records[index], superseded_by=replacement.id, updated_at=datetime.now(timezone.utc).isoformat())
    updated.append(replacement)
    reason = "memory_superseded"
    return updated, MemoryWriteDecision("supersede", reason, replacement, _memory_audit_event("supersede", reason, replacement))


def _normalize_memory_text(value: str) -> str:
    return " ".join(value.lower().split())


def _memory_created_at_value(record: MemoryRecord) -> datetime:
    try:
        return datetime.fromisoformat(record.created_at)
    except ValueError:
        return datetime.now(timezone.utc)


def score_memory_relevance(record: MemoryRecord, role: str, current_facts: set[str] | None = None) -> float:
    facts = current_facts or set()
    score = 0.0
    scope_weights = {"user": 3.0, "project": 2.0, "workflow": 1.0}
    score += scope_weights.get(record.scope, 0.0)
    score += min(max(record.confidence, 0.0), 1.0)
    if record.source:
        score += 0.5
    if role and role.lower() in record.content.lower():
        score += 0.25
    if record.content in facts:
        score -= 100.0
    if record.is_expired():
        score -= 50.0
    if record.superseded_by:
        score -= 25.0
    age_days = max(0.0, (datetime.now(timezone.utc) - _memory_created_at_value(record)).days)
    if age_days <= 7:
        score += 0.75
    elif age_days <= 30:
        score += 0.5
    elif age_days <= 180:
        score += 0.25
    return score


def memory_record_key(record: MemoryRecord) -> tuple[str, str, str]:
    return (
        record.scope,
        _normalize_memory_text(record.content),
        _normalize_memory_text(record.source),
    )


def dedupe_memory_records(records: list[MemoryRecord]) -> tuple[list[MemoryRecord], list[dict[str, str]]]:
    kept: dict[tuple[str, str, str], tuple[float, int, MemoryRecord]] = {}
    duplicates: list[dict[str, str]] = []
    for index, record in enumerate(records):
        key = memory_record_key(record)
        score = score_memory_relevance(record, role="")
        current = kept.get(key)
        if current is None:
            kept[key] = (score, index, record)
            continue
        current_score, _, current_record = current
        current_created = _memory_created_at_value(current_record)
        record_created = _memory_created_at_value(record)
        keep_new_record = score > current_score or (score == current_score and record_created > current_created)
        if keep_new_record:
            duplicates.append({
                "type": "memory",
                "duplicate_id": current_record.id,
                "kept_id": record.id,
                "scope": record.scope,
                "source": record.source,
                "reason": "duplicate_replaced",
            })
            kept[key] = (score, index, record)
        else:
            duplicates.append({
                "type": "memory",
                "duplicate_id": record.id,
                "kept_id": current_record.id,
                "scope": record.scope,
                "source": record.source,
                "reason": "duplicate_skipped",
            })
    unique_records = [entry[2] for entry in sorted(kept.values(), key=lambda item: item[1])]
    return unique_records, duplicates


def build_memory_audit_entries(records: list[MemoryRecord], role: str = "engineer", current_facts: set[str] | None = None) -> list[dict[str, str]]:
    facts = current_facts or set()
    unique_records, duplicates = dedupe_memory_records(records)
    unique_ids = {record.id for record in unique_records}
    duplicate_map = {entry["duplicate_id"]: entry for entry in duplicates}
    entries: list[dict[str, str]] = []
    for record in records:
        if record.id in duplicate_map:
            duplicate_entry = duplicate_map[record.id]
            entries.append({
                "type": "memory",
                "id": record.id,
                "scope": record.scope,
                "source": record.source,
                "status": "duplicate",
                "reason": duplicate_entry["reason"],
                "score": f"{score_memory_relevance(record, role, facts):.2f}",
                "duplicate_of": duplicate_entry["kept_id"],
            })
            continue
        status = "active"
        reason = "selected"
        if record.is_expired():
            status = "expired"
            reason = "expired"
        elif record.superseded_by:
            status = "superseded"
            reason = "superseded"
        elif record.content in facts:
            status = "conflict"
            reason = "current_fact_preferred"
        elif record.id not in unique_ids:
            status = "duplicate"
            reason = "duplicate_skipped"
        entries.append({
            "type": "memory",
            "id": record.id,
            "scope": record.scope,
            "source": record.source,
            "status": status,
            "reason": reason,
            "score": f"{score_memory_relevance(record, role, facts):.2f}",
        })
    return entries


def select_memory_for_context(
    records: list[MemoryRecord],
    role: str,
    allowed_scopes: set[MemoryScope] | None = None,
    current_facts: set[str] | None = None,
) -> tuple[list[MemoryRecord], list[dict[str, str]]]:
    scopes = allowed_scopes or LONG_TERM_SCOPES
    facts = current_facts or set()
    deduped_records, duplicates = dedupe_memory_records(records)
    selected: list[MemoryRecord] = []
    sources: list[dict[str, str]] = []
    duplicate_map = {entry["duplicate_id"]: entry for entry in duplicates}
    ordered_records = sorted(
        deduped_records,
        key=lambda record: score_memory_relevance(record, role, facts),
        reverse=True,
    )
    for record in ordered_records:
        memory_id = record.id
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
            "reason": "score_and_scope_match",
        })
    for record in records:
        duplicate = duplicate_map.get(record.id)
        if duplicate:
            sources.append({
                "type": "memory",
                "name": record.id,
                "scope": record.scope,
                "source": record.source,
                "status": "duplicate",
                "reason": duplicate["reason"],
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


class MemoryStore:
    def __init__(self, store_path: Path):
        self.path = store_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        records: list[MemoryRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(_memory_record_from_dict(json.loads(line)))
        return records

    def save(self, records: list[MemoryRecord]) -> Path:
        payload = "\n".join(json.dumps(_memory_record_to_dict(record), ensure_ascii=False) for record in records)
        if payload:
            payload += "\n"
        self.path.write_text(payload, encoding="utf-8")
        return self.path

    def append(self, record: MemoryRecord) -> Path:
        records = self.load()
        records.append(record)
        return self.save(records)

    def replace(self, records: list[MemoryRecord]) -> Path:
        return self.save(records)


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
