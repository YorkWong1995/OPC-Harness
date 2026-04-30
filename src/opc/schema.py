"""OPC 核心数据结构定义"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


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
