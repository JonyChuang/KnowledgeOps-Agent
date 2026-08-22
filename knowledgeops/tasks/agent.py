"""Request-scoped runtime factory for the Agent HTTP API."""

from dataclasses import dataclass

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.chat import (
    ChatAnswerGenerator,
    OpenAIChatAnswerGenerator,
    UnavailableChatAnswerGenerator,
)
from ..agents.function_calling import (
    FunctionCallingAgent,
    OpenAIFunctionCallingAgent,
    TicketIntakeGuardedFunctionCallingAgent,
)
from ..agents.llm_router import OpenAIIntentRouter
from ..agents.router import FallbackIntentRouter, IntentRouter, KeywordIntentRouter
from ..agents.ticket_tools import (
    ConfirmedTicketCreationTool,
    ServiceTicketQueryTool,
)
from ..agents.tools import (
    DatabaseKnowledgeBaseScopeTool,
    LazyKnowledgeSearchTool,
)
from ..agents.workflow import AgentDependencies
from ..config import Settings
from ..repositories import DocumentChunkRepository
from ..services import TicketService
from .indexing import build_hybrid_retriever


@dataclass
class AgentRuntime:
    """Own Agent dependencies and the external resource cleanup boundary."""

    dependencies: AgentDependencies
    knowledge_search: LazyKnowledgeSearchTool

    async def close(self) -> None:
        """Close a retriever only when this request actually created one."""
        await self.knowledge_search.close()


def build_chat_answer_generator(
    settings: Settings,
) -> ChatAnswerGenerator:
    if (
        not settings.chat_model
        or settings.chat_api_key is None
        or not settings.chat_base_url
    ):
        return UnavailableChatAnswerGenerator()

    client = AsyncOpenAI(
        api_key=settings.chat_api_key.get_secret_value(),
        base_url=settings.chat_base_url,
    )
    return OpenAIChatAnswerGenerator(
        client=client,
        model=settings.chat_model,
        temperature=settings.chat_temperature,
    )


def build_intent_router(settings: Settings) -> IntentRouter:
    if not settings.chat_model or settings.chat_api_key is None:
        return KeywordIntentRouter()

    client = AsyncOpenAI(
        api_key=settings.chat_api_key.get_secret_value(),
        base_url=settings.chat_base_url,
    )
    return FallbackIntentRouter(
        primary=OpenAIIntentRouter(
            client=client,
            model=settings.chat_model,
            temperature=settings.chat_temperature,
        ),
        fallback=KeywordIntentRouter(),
    )


def build_function_calling_agent(
    settings: Settings,
) -> FunctionCallingAgent | None:
    """Create the model-selected tool loop only with complete Chat credentials."""
    if (
        not settings.chat_model
        or settings.chat_api_key is None
        or not settings.chat_base_url
    ):
        return None

    client = AsyncOpenAI(
        api_key=settings.chat_api_key.get_secret_value(),
        base_url=settings.chat_base_url,
    )
    return TicketIntakeGuardedFunctionCallingAgent(
        OpenAIFunctionCallingAgent(
            client=client,
            model=settings.chat_model,
            temperature=settings.chat_temperature,
        )
    )


def build_agent_runtime(
    session: AsyncSession,
    settings: Settings,
) -> AgentRuntime:
    """Assemble fresh request-scoped Agent dependencies."""

    knowledge_search = LazyKnowledgeSearchTool(
        lambda: build_hybrid_retriever(settings)
    )
    knowledge_base_scope = DatabaseKnowledgeBaseScopeTool(
        DocumentChunkRepository(session)
    )
    chat_answer_generator = build_chat_answer_generator(settings)
    ticket_service = TicketService(session)
    intent_router = build_intent_router(settings)

    return AgentRuntime(
        dependencies=AgentDependencies(
            intent_router=intent_router,
            knowledge_search=knowledge_search,
            chat_answer_generator=chat_answer_generator,
            ticket_query=ServiceTicketQueryTool(ticket_service),
            ticket_creation=ConfirmedTicketCreationTool(ticket_service),
            knowledge_base_scope=knowledge_base_scope,
            function_calling_agent=build_function_calling_agent(settings),
        ),
        knowledge_search=knowledge_search,
    )
