"""LLM 答案生成：复用 Agent 类，基于检索结果生成带引用的回答

防幻觉策略：
1. 严格 prompt：没有就说不存在，禁止脑补
2. 强制标注来源：每句话必须标注出处
3. 分离事实和推断：让用户区分文档说的和 AI 猜的
"""

from __future__ import annotations

from ..agent import Agent
from .models import FusedResult

KNOWLEDGE_QA_PROMPT = """你是一个严格的文档问答助手。你只能基于检索到的代码和文档片段回答问题。

核心规则（必须遵守）：
1. 只使用检索结果中【明确提到】的信息回答
2. 检索结果中没有的内容，一律回答"文档中未提及"
3. 绝对不要根据你自己的训练知识补充内容
4. 绝对不要推测、脑补、扩展
5. 如果检索结果不足以回答问题，直接说"根据现有文档无法回答"
6. 代码和技术术语保持原文，其他用中文回答

回答格式（必须按此格式）：

## 事实（来自文档）
- 每个事实陈述后面必须标注 [来源: 文件路径:行号]
- 无法标注来源的陈述不要写

## 推断（文档中未明确说明，基于通用知识）
- 这里只能写你从通用知识推断的内容
- 每条必须以"（推断）"开头
- 如果没有推断内容，写"无"

## 结论
- 一句话总结

示例：

## 事实（来自文档）
- 初始化函数为 init_camera(port, baudrate) [来源: sdk.py:15-22]
- 支持 COM1-COM9 [来源: README.md:23]
- 默认波特率 9600 [来源: sdk.py:16]

## 推断（文档中未明确说明，基于通用知识）
- （推断）COM10 及以上端口可能不支持，但文档未明确说明

## 结论
- 使用 init_camera 初始化，支持 COM1-COM9，文档未提及 COM10 支持。
"""


class AnswerGenerator:
    """基于检索结果生成答案"""

    def __init__(self, model: str | None = None):
        self.agent = Agent(
            role="knowledge_assistant",
            system_prompt=KNOWLEDGE_QA_PROMPT,
            model=model,
        )

    def generate(self, query: str, results: list[FusedResult]) -> str:
        """基于检索结果生成答案"""
        context = self._format_context(results)
        prompt = (
            f"以下是检索到的代码和文档片段（每段标注了文件路径和行号）：\n\n"
            f"--- 检索结果开始 ---\n{context}\n--- 检索结果结束 ---\n\n"
            f"问题：{query}\n\n"
            f"请严格按照规则回答：只使用上述检索结果中明确提到的信息，"
            f"每个事实必须标注[来源: 文件路径:行号]，没有就说不存在。"
        )
        return self.agent.run(prompt)

    def _format_context(self, results: list[FusedResult]) -> str:
        """格式化检索结果为上下文"""
        parts = []
        for i, r in enumerate(results, 1):
            chunk = r.chunk
            source_info = f"[{i}] {chunk.file_path}:{chunk.start_line}-{chunk.end_line}"

            # 截断过长的内容
            content = chunk.content
            if len(content) > 1500:
                content = content[:1500] + "\n... (截断)"

            parts.append(f"{source_info}\n```\n{content}\n```")

        return "\n\n".join(parts)
