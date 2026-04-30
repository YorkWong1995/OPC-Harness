"""Memory: 角色记忆系统

参考 MetaGPT 的 Memory 设计，提供：
1. 消息存储和检索
2. 按角色/Action 类型索引
3. 工作记忆和长期记忆的区分
"""

from typing import List, Optional, Set, Dict
from .schema import Message


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
