"""Environment: 角色协作的消息总线

参考 MetaGPT 的 Environment 设计，提供：
1. 角色注册和管理
2. 消息发布和订阅
3. 消息历史记录
"""

from typing import Dict, List, Optional, Set
from pathlib import Path
import asyncio

from .schema import Message, MessageQueue
from .agent import Agent
from .run_store import RunStore


class Environment:
    """环境：角色协作的消息总线

    核心职责：
    1. 管理所有角色
    2. 路由消息到订阅的角色
    3. 记录消息历史
    """

    def __init__(self, project_dir: Optional[Path] = None, run_store: Optional[RunStore] = None):
        self.project_dir = project_dir
        self.roles: Dict[str, Agent] = {}  # 角色名 -> Agent
        self.message_history: List[Message] = []  # 全局消息历史
        self._subscriptions: Dict[str, Set[str]] = {}  # 角色名 -> 订阅的消息类型
        self.run_store = run_store or self._create_run_store(project_dir)

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
        message.validate_route(self._known_route_roles())
        # 记录到历史
        self.message_history.append(message)
        self._persist_message("message_published", message)
        print(f"[Environment] 发布消息: [{message.role}] -> {message.send_to or 'all'}")

        # 路由到订阅的角色
        for role_name, agent in self.roles.items():
            # 检查消息是否发送给该角色
            if message.is_sent_to(role_name):
                # 检查角色是否订阅了该类型的消息
                if self._is_subscribed(role_name, message):
                    self._deliver_message(role_name, message)

    async def publish_async(self, message: Message):
        """异步发布消息，并并行投递给订阅角色。"""
        message.validate_route(self._known_route_roles())
        self.message_history.append(message)
        self._persist_message("message_published", message)
        print(f"[Environment] 异步发布消息: [{message.role}] -> {message.send_to or 'all'}")

        tasks = []
        for role_name in self.roles:
            if message.is_sent_to(role_name) and self._is_subscribed(role_name, message):
                tasks.append(self._deliver_message_async(role_name, message))
        if tasks:
            await asyncio.gather(*tasks)

    def _create_run_store(self, project_dir: Optional[Path]) -> Optional[RunStore]:
        if project_dir is None:
            return None
        return RunStore(project_dir / "artifacts")

    def _persist_message(self, event_type: str, message: Message):
        if self.run_store is None:
            return
        self.run_store.append(event_type, message=self._message_payload(message))

    def _persist_delivery(self, role_name: str, message: Message, buffer_size: int):
        if self.run_store is None:
            return
        self.run_store.append(
            "message_delivered",
            recipient=role_name,
            buffer_size=buffer_size,
            message=self._message_payload(message),
        )

    def _message_payload(self, message: Message) -> dict:
        return message.model_dump(mode="json")

    def _known_route_roles(self) -> set[str]:
        return set(self.roles) | {"all", "system"}

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
            self._persist_delivery(role_name, message, len(agent.msg_buffer))
            print(f"[Environment]   -> 投递给 {role_name}")

    async def _deliver_message_async(self, role_name: str, message: Message):
        """异步将消息投递给角色。"""
        agent = self.roles[role_name]
        if hasattr(agent, "receive"):
            await asyncio.to_thread(agent.receive, message)
            self._persist_delivery(role_name, message, len(agent.msg_buffer))
            print(f"[Environment]   -> 异步投递给 {role_name}")

    async def dispatch_pending(self) -> dict[str, list[str]]:
        """并行驱动所有有待处理消息的 Agent。"""
        tasks = {
            role_name: agent.observe_think_act()
            for role_name, agent in self.roles.items()
            if hasattr(agent, "observe_think_act") and agent.has_pending_messages()
        }
        if not tasks:
            return {}
        results = await asyncio.gather(*tasks.values())
        return dict(zip(tasks.keys(), results))

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
