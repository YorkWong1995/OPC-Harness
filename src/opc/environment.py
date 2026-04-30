"""Environment: 角色协作的消息总线

参考 MetaGPT 的 Environment 设计，提供：
1. 角色注册和管理
2. 消息发布和订阅
3. 消息历史记录
"""

from typing import Dict, List, Optional, Set
from pathlib import Path

from .schema import Message, MessageQueue
from .agent import Agent


class Environment:
    """环境：角色协作的消息总线

    核心职责：
    1. 管理所有角色
    2. 路由消息到订阅的角色
    3. 记录消息历史
    """

    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = project_dir
        self.roles: Dict[str, Agent] = {}  # 角色名 -> Agent
        self.message_history: List[Message] = []  # 全局消息历史
        self._subscriptions: Dict[str, Set[str]] = {}  # 角色名 -> 订阅的消息类型

    def add_role(self, name: str, agent: Agent):
        """添加角色到环境"""
        self.roles[name] = agent
        self._subscriptions[name] = set()  # 初始化订阅列表
        print(f"[Environment] 添加角色: {name}")

    def remove_role(self, name: str):
        """从环境中移除角色"""
        if name in self.roles:
            del self.roles[name]
            del self._subscriptions[name]
            print(f"[Environment] 移除角色: {name}")

    def subscribe(self, role_name: str, message_types: Set[str]):
        """角色订阅特定类型的消息

        Args:
            role_name: 角色名
            message_types: 订阅的消息类型集合（如 {"prd", "architecture"}）
        """
        if role_name not in self._subscriptions:
            self._subscriptions[role_name] = set()
        self._subscriptions[role_name].update(message_types)
        print(f"[Environment] {role_name} 订阅: {message_types}")

    def publish(self, message: Message):
        """发布消息到环境

        消息会被：
        1. 记录到历史
        2. 路由到订阅的角色
        """
        # 记录到历史
        self.message_history.append(message)
        print(f"[Environment] 发布消息: [{message.role}] -> {message.send_to or 'all'}")

        # 路由到订阅的角色
        for role_name, agent in self.roles.items():
            # 检查消息是否发送给该角色
            if message.is_sent_to(role_name):
                # 检查角色是否订阅了该类型的消息
                if self._is_subscribed(role_name, message):
                    self._deliver_message(role_name, message)

    def _is_subscribed(self, role_name: str, message: Message) -> bool:
        """检查角色是否订阅了该消息"""
        subscriptions = self._subscriptions.get(role_name, set())

        # 如果没有订阅任何类型，默认接收所有消息
        if not subscriptions:
            return True

        # 检查是否订阅了该消息类型
        if message.cause_by and message.cause_by in subscriptions:
            return True

        # 检查是否订阅了发送者角色
        if message.role in subscriptions:
            return True

        return False

    def _deliver_message(self, role_name: str, message: Message):
        """将消息投递给角色"""
        agent = self.roles[role_name]
        if hasattr(agent, "receive"):
            agent.receive(message)
            print(f"[Environment]   -> 投递给 {role_name}")

    def get_history(self, role: Optional[str] = None, limit: int = 100) -> List[Message]:
        """获取消息历史

        Args:
            role: 过滤特定角色的消息，None 表示所有消息
            limit: 最多返回多少条消息

        Returns:
            消息列表（最新的在前）
        """
        if role:
            filtered = [msg for msg in self.message_history if msg.role == role]
        else:
            filtered = self.message_history

        return filtered[-limit:]

    def is_idle(self) -> bool:
        """检查环境是否空闲（所有角色都没有待处理消息）"""
        for agent in self.roles.values():
            if hasattr(agent, "has_pending_messages") and agent.has_pending_messages():
                return False
        return True

    def reset(self):
        """重置环境（清空消息历史）"""
        self.message_history.clear()
        print("[Environment] 环境已重置")

    def __repr__(self) -> str:
        return f"Environment(roles={list(self.roles.keys())}, messages={len(self.message_history)})"
