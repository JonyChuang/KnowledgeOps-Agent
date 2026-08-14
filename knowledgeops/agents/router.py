"""Pure intent routing for the KnowledgeOps Agent workflow."""

from __future__ import annotations

import re
from typing import Protocol

from .state import AgentIntent

_GENERAL_CHAT_PATTERN = re.compile(
    r"^(?:你好|您好|嗨|哈喽|hello|hi|在吗|有人吗)[！!。？?\s]*$",
    re.IGNORECASE,
)


def is_general_chat_message(user_message: str) -> bool:
    """Recognize greetings before an optional model router can over-classify them."""
    return bool(_GENERAL_CHAT_PATTERN.fullmatch(user_message.strip()))


class IntentRouter(Protocol):
    """Classify a user message without performing any business action."""

    async def route(self, user_message: str) -> AgentIntent | None:
        """Return one supported intent or None when the message is unclear."""


class KeywordIntentRouter:
    """Deterministic offline baseline for intent routing."""

    _HOW_TO_TICKET_PATTERN = re.compile(
        r"(?:如何|怎么|怎样|是否|能否).{0,16}(?:创建|新建|提交|开|提).{0,6}工单"
        r"|(?:创建|新建|提交|开|提).{0,6}工单.{0,16}(?:流程|方法|步骤|规则|说明)"
    )
    _CREATE_TICKET_PATTERN = re.compile(
        r"(?:创建|新建|提交|开|提)(?:一个|一张|个|张)?"
        r"[^。！？?!\r\n]{0,40}工单"
        r"|(?:我要|请|帮我|麻烦).{0,8}(?:报修|报障)"
    )
    _QUERY_TICKET_PATTERN = re.compile(
        r"(?:查询|查看|检索|跟进|追踪).{0,12}工单"
        r"|工单.{0,12}(?:状态|进度|查询|详情|怎么查|如何查|怎么查看|如何查看)"
    )
    _QUESTION_PATTERN = re.compile(
        r"[?？]|(?:什么|为何|为什么|如何|怎么|怎样|是否|能否)"
    )

    async def route(self, user_message: str) -> AgentIntent | None:
        """Classify safely; unclear input never becomes a write intent."""
        message = user_message.strip()
        if not message:
            return None

        if is_general_chat_message(message):
            return AgentIntent.GENERAL_CHAT

        if self._HOW_TO_TICKET_PATTERN.search(message):
            return AgentIntent.KNOWLEDGE_QA

        if self._CREATE_TICKET_PATTERN.search(message):
            return AgentIntent.TICKET_CREATE

        if self._QUERY_TICKET_PATTERN.search(message):
            return AgentIntent.TICKET_QUERY

        if self._QUESTION_PATTERN.search(message):
            return AgentIntent.KNOWLEDGE_QA

        # A non-empty request that does not map to a read/write business tool is
        # still a valid conversational turn when a Chat model is configured.
        return AgentIntent.GENERAL_CHAT


class FallbackIntentRouter:
    """优先使用模型路由；模型不可用时回退到确定性的关键词规则。"""

    def __init__(
        self,
        *,
        primary: IntentRouter,
        fallback: IntentRouter,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    async def route(self, user_message: str) -> AgentIntent | None:
        if is_general_chat_message(user_message):
            return AgentIntent.GENERAL_CHAT

        try:
            intent = await self.primary.route(user_message)
        except Exception:  # noqa: BLE001 - model routing must fail closed to safe fallback
            intent = None

        if intent is not None:
            return intent

        return await self.fallback.route(user_message)
