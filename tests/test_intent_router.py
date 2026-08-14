import pytest

from knowledgeops.agents.router import FallbackIntentRouter, KeywordIntentRouter
from knowledgeops.agents.state import AgentIntent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("请帮我创建一个 VPN 无法连接的工单", AgentIntent.TICKET_CREATE),
        ("查看工单 T-1001 的状态", AgentIntent.TICKET_QUERY),
        ("VPN 接入流程是什么？", AgentIntent.KNOWLEDGE_QA),
        ("如何创建工单？", AgentIntent.KNOWLEDGE_QA),
    ],
)
async def test_router_classifies_supported_messages(
    message: str,
    expected: AgentIntent,
) -> None:
    router = KeywordIntentRouter()

    result = await router.route(message)

    assert result == expected


@pytest.mark.asyncio
async def test_router_sends_an_unsupported_message_to_general_chat() -> None:
    router = KeywordIntentRouter()

    result = await router.route("帮我处理一下")

    assert result == AgentIntent.GENERAL_CHAT


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["你好", "您好！", "hello", "在吗？"])
async def test_router_routes_greetings_to_bounded_general_chat(
    message: str,
) -> None:
    router = KeywordIntentRouter()

    result = await router.route(message)

    assert result == AgentIntent.GENERAL_CHAT


@pytest.mark.asyncio
async def test_router_returns_none_for_blank_message() -> None:
    router = KeywordIntentRouter()

    result = await router.route("   ")

    assert result is None

class FailingRouter:
    async def route(self, user_message: str) -> AgentIntent | None:
        raise RuntimeError("Chat service unavailable")


class StaticRouter:
    def __init__(self, intent: AgentIntent | None) -> None:
        self.intent = intent

    async def route(self, user_message: str) -> AgentIntent | None:
        return self.intent


@pytest.mark.asyncio
async def test_fallback_router_uses_keyword_router_when_primary_fails() -> None:
    router = FallbackIntentRouter(
        primary=FailingRouter(),
        fallback=KeywordIntentRouter(),
    )

    result = await router.route("请帮我创建一个 VPN 无法连接的工单")

    assert result == AgentIntent.TICKET_CREATE


@pytest.mark.asyncio
async def test_fallback_router_prefers_llm_result() -> None:
    router = FallbackIntentRouter(
        primary=StaticRouter(AgentIntent.KNOWLEDGE_QA),
        fallback=KeywordIntentRouter(),
    )

    result = await router.route("随便一句不含关键词的话")

    assert result == AgentIntent.KNOWLEDGE_QA
