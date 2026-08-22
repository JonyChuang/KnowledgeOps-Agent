from datetime import datetime, timezone

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from knowledgeops.agents import (
    AgentCitation,
    AgentConversationMessage,
    AgentDependencies,
    AgentIntent,
    AgentState,
    ConfirmationStatus,
    build_agent_graph,
)
from knowledgeops.models import TicketPriority, TicketStatus
from knowledgeops.schemas import TicketRead


class FakeIntentRouter:
    def __init__(self, intent: AgentIntent) -> None:
        self.intent = intent
        self.messages: list[str] = []

    async def route(self, user_message: str) -> AgentIntent:
        self.messages.append(user_message)
        return self.intent


class FakeKnowledgeSearchTool:
    def __init__(self, citations: list[AgentCitation]) -> None:
        self.citations = citations
        self.calls: list[tuple[str, str, int]] = []

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[AgentCitation]:
        self.calls.append((query, knowledge_base_id, limit))
        return self.citations


class FakeKnowledgeBaseScopeTool:
    def __init__(self, citations: list[AgentCitation]) -> None:
        self.citations = citations
        self.calls: list[tuple[str, int]] = []

    async def list_ready_citations(
        self,
        *,
        knowledge_base_id: str,
        limit: int = 3,
    ) -> list[AgentCitation]:
        self.calls.append((knowledge_base_id, limit))
        return self.citations


class FakeChatAnswerGenerator:
    def __init__(self) -> None:
        self.general_chat_calls: list[tuple[str, list[AgentConversationMessage]]] = []

    async def answer_general_chat(
        self,
        user_message: str,
        conversation_history: list[AgentConversationMessage],
    ) -> str:
        self.general_chat_calls.append((user_message, conversation_history))
        return f"对话回复：{user_message}"

    async def answer_from_citations(
        self,
        question: str,
        citations: list[AgentCitation],
    ) -> str:
        return "根据知识库：VPN 连接需要使用企业账号。"


class FakeTicketQueryTool:
    def __init__(self, tickets: list[TicketRead]) -> None:
        self.tickets = tickets
        self.calls: list[tuple[str, int]] = []

    async def list_tickets(
        self,
        *,
        actor: str,
        limit: int = 20,
    ) -> list[TicketRead]:
        self.calls.append((actor, limit))
        return self.tickets


class FakeTicketCreationTool:
    def __init__(self, ticket: TicketRead) -> None:
        self.ticket = ticket
        self.states: list[AgentState] = []

    async def create_from_state(self, state: AgentState) -> TicketRead:
        self.states.append(state)
        return self.ticket


def make_citation() -> AgentCitation:
    return AgentCitation(
        chunk_id="chunk-001",
        document_id="document-001",
        source_name="vpn-guide.md",
        source_type="markdown",
        chunk_index=0,
        start_char=0,
        end_char=18,
        text="VPN 连接需要使用企业账号。",
        score=0.91,
        sources=["vector", "keyword"],
        rerank_score=0.88,
    )


def make_ticket() -> TicketRead:
    now = datetime.now(timezone.utc)
    return TicketRead(
        id="ticket-001",
        title="VPN 无法连接",
        description="测试工单内容。",
        priority=TicketPriority.HIGH,
        status=TicketStatus.OPEN,
        requester="alice",
        created_at=now,
        updated_at=now,
    )


def build_dependencies(
    intent: AgentIntent,
) -> tuple[
    AgentDependencies,
    FakeKnowledgeSearchTool,
    FakeTicketQueryTool,
    FakeTicketCreationTool,
]:
    knowledge_search = FakeKnowledgeSearchTool([make_citation()])
    ticket_query = FakeTicketQueryTool([make_ticket()])
    ticket_creation = FakeTicketCreationTool(make_ticket())
    chat_answer_generator = FakeChatAnswerGenerator()

    dependencies = AgentDependencies(
        intent_router=FakeIntentRouter(intent),
        knowledge_search=knowledge_search,
        chat_answer_generator=chat_answer_generator,
        ticket_query=ticket_query,
        ticket_creation=ticket_creation,
    )
    return dependencies, knowledge_search, ticket_query, ticket_creation


@pytest.mark.asyncio
async def test_workflow_answers_knowledge_question_with_citations() -> None:
    dependencies, knowledge_search, _, ticket_creation = build_dependencies(
        AgentIntent.KNOWLEDGE_QA
    )
    graph = build_agent_graph(dependencies)
    config = {"configurable": {"thread_id": "knowledge-1"}}

    result = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message="VPN 怎么连接？",
            knowledge_base_id="kb-001",
        ).model_dump(mode="json"),
        config=config,
    )
    state = AgentState.model_validate(result)

    assert state.intent == AgentIntent.KNOWLEDGE_QA
    assert state.answer == "根据知识库：VPN 连接需要使用企业账号。"
    assert state.citations[0].chunk_id == "chunk-001"
    assert knowledge_search.calls == [("VPN 怎么连接？", "kb-001", 5)]
    assert ticket_creation.states == []


@pytest.mark.asyncio
async def test_workflow_answers_general_chat_without_calling_tools() -> None:
    dependencies, knowledge_search, ticket_query, ticket_creation = build_dependencies(
        AgentIntent.GENERAL_CHAT
    )
    graph = build_agent_graph(dependencies)

    result = await graph.ainvoke(
        AgentState(actor="alice", user_message="你好").model_dump(mode="json"),
        config={"configurable": {"thread_id": "general-chat-1"}},
    )
    state = AgentState.model_validate(result)

    assert state.intent == AgentIntent.GENERAL_CHAT
    assert state.answer == "对话回复：你好"
    assert state.citations == []
    assert knowledge_search.calls == []
    assert ticket_query.calls == []
    assert ticket_creation.states == []


@pytest.mark.asyncio
async def test_workflow_passes_recent_conversation_to_general_chat() -> None:
    dependencies, knowledge_search, ticket_query, ticket_creation = build_dependencies(
        AgentIntent.GENERAL_CHAT
    )
    chat_answer_generator = dependencies.chat_answer_generator
    assert isinstance(chat_answer_generator, FakeChatAnswerGenerator)
    history = [
        AgentConversationMessage(role="user", content="我在排查 VPN 问题。"),
        AgentConversationMessage(role="assistant", content="请告诉我具体报错。"),
    ]
    graph = build_agent_graph(dependencies)

    result = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message="刚才提到的问题先记录一下。",
            conversation_history=history,
        ).model_dump(mode="json"),
        config={"configurable": {"thread_id": "general-chat-history-1"}},
    )
    state = AgentState.model_validate(result)

    assert state.answer == "对话回复：刚才提到的问题先记录一下。"
    assert chat_answer_generator.general_chat_calls == [
        ("刚才提到的问题先记录一下。", history)
    ]
    assert knowledge_search.calls == []
    assert ticket_query.calls == []
    assert ticket_creation.states == []


@pytest.mark.asyncio
async def test_workflow_explains_scope_when_query_has_no_direct_match() -> None:
    scope_citation = make_citation().model_copy(
        update={
            "source_name": "vpn-runbook.md",
            "sources": ["knowledge_base_scope"],
            "score": 0.0,
        }
    )
    scope_tool = FakeKnowledgeBaseScopeTool([scope_citation])
    ticket_query = FakeTicketQueryTool([])
    ticket_creation = FakeTicketCreationTool(make_ticket())
    dependencies = AgentDependencies(
        intent_router=FakeIntentRouter(AgentIntent.KNOWLEDGE_QA),
        knowledge_search=FakeKnowledgeSearchTool([]),
        chat_answer_generator=FakeChatAnswerGenerator(),
        ticket_query=ticket_query,
        ticket_creation=ticket_creation,
        knowledge_base_scope=scope_tool,
    )
    graph = build_agent_graph(dependencies)

    result = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message="summarize engineering standards",
            knowledge_base_id="kb-001",
        ).model_dump(mode="json"),
        config={"configurable": {"thread_id": "scope-1"}},
    )
    state = AgentState.model_validate(result)

    assert "vpn-runbook.md" in state.answer
    assert state.citations == [scope_citation]
    assert scope_tool.calls == [("kb-001", 3)]


@pytest.mark.asyncio
async def test_workflow_keeps_empty_result_for_an_empty_knowledge_base() -> None:
    scope_tool = FakeKnowledgeBaseScopeTool([])
    dependencies = AgentDependencies(
        intent_router=FakeIntentRouter(AgentIntent.KNOWLEDGE_QA),
        knowledge_search=FakeKnowledgeSearchTool([]),
        chat_answer_generator=FakeChatAnswerGenerator(),
        ticket_query=FakeTicketQueryTool([]),
        ticket_creation=FakeTicketCreationTool(make_ticket()),
        knowledge_base_scope=scope_tool,
    )
    graph = build_agent_graph(dependencies)

    result = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message="summarize engineering standards",
            knowledge_base_id="empty-kb",
        ).model_dump(mode="json"),
        config={"configurable": {"thread_id": "scope-empty-1"}},
    )
    state = AgentState.model_validate(result)

    assert state.citations == []
    assert scope_tool.calls == [("empty-kb", 3)]


@pytest.mark.asyncio
async def test_workflow_lists_only_the_current_actors_tickets() -> None:
    dependencies, _, ticket_query, ticket_creation = build_dependencies(
        AgentIntent.TICKET_QUERY
    )
    graph = build_agent_graph(dependencies)
    config = {"configurable": {"thread_id": "tickets-1"}}

    result = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message="查看我的工单",
        ).model_dump(mode="json"),
        config=config,
    )
    state = AgentState.model_validate(result)

    assert state.ticket_ids == ["ticket-001"]
    assert state.answer == "你当前共有 1 张工单：\n1. VPN 无法连接｜待受理｜高优先级｜处理人：暂未分配"
    assert ticket_query.calls == [("alice", 20)]
    assert ticket_creation.states == []


@pytest.mark.asyncio
async def test_workflow_interrupts_before_creating_a_ticket() -> None:
    dependencies, _, _, ticket_creation = build_dependencies(
        AgentIntent.TICKET_CREATE
    )
    graph = build_agent_graph(dependencies)
    config = {"configurable": {"thread_id": "ticket-create-1"}}

    interrupted = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message=(
                "VPN 在 Windows 11 客户端报错 619，重启后仍失败，"
                "已持续三十分钟，只影响我本人，请创建工单。"
            ),
        ).model_dump(mode="json"),
        config=config,
    )

    assert "__interrupt__" in interrupted
    assert interrupted["confirmation_status"] == ConfirmationStatus.PENDING
    assert ticket_creation.states == []

    completed = await graph.ainvoke(Command(resume=True), config=config)
    state = AgentState.model_validate(completed)

    assert state.confirmation_status == ConfirmationStatus.CONFIRMED
    assert state.created_ticket_id == "ticket-001"
    assert len(ticket_creation.states) == 1
    assert ticket_creation.states[0].can_create_ticket is True


@pytest.mark.asyncio
async def test_workflow_rejects_ticket_creation_when_confirmation_is_false() -> None:
    dependencies, _, _, ticket_creation = build_dependencies(
        AgentIntent.TICKET_CREATE
    )
    graph = build_agent_graph(dependencies)
    config = {"configurable": {"thread_id": "ticket-reject-1"}}

    await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message=(
                "VPN 在 Windows 11 客户端报错 619，重启后仍失败，"
                "已持续三十分钟，只影响我本人，请创建工单。"
            ),
        ).model_dump(mode="json"),
        config=config,
    )
    completed = await graph.ainvoke(Command(resume=False), config=config)
    state = AgentState.model_validate(completed)

    assert state.confirmation_status == ConfirmationStatus.REJECTED
    assert state.answer == "已取消创建工单。"
    assert ticket_creation.states == []

@pytest.mark.asyncio
async def test_workflow_can_resume_with_a_new_graph_and_shared_checkpointer() -> None:
    checkpointer = MemorySaver()
    first_dependencies, _, _, first_ticket_creation = build_dependencies(
        AgentIntent.TICKET_CREATE
    )
    config = {"configurable": {"thread_id": "shared-checkpointer-1"}}

    first_graph = build_agent_graph(
        first_dependencies,
        checkpointer=checkpointer,
    )
    interrupted = await first_graph.ainvoke(
        AgentState(
            actor="alice",
            user_message=(
                "VPN 在 Windows 11 客户端报错 619，重启后仍失败，"
                "已持续三十分钟，只影响我本人，请创建工单。"
            ),
        ).model_dump(mode="json"),
        config=config,
    )

    assert "__interrupt__" in interrupted
    assert first_ticket_creation.states == []

    resumed_dependencies, _, _, resumed_ticket_creation = build_dependencies(
        AgentIntent.TICKET_CREATE
    )
    resumed_graph = build_agent_graph(
        resumed_dependencies,
        checkpointer=checkpointer,
    )
    completed = await resumed_graph.ainvoke(
        Command(resume=True),
        config=config,
    )
    state = AgentState.model_validate(completed)

    assert state.created_ticket_id == "ticket-001"
    assert len(resumed_ticket_creation.states) == 1


@pytest.mark.asyncio
async def test_workflow_clarifies_incomplete_ticket_request_before_confirmation() -> None:
    dependencies, _, _, ticket_creation = build_dependencies(AgentIntent.TICKET_CREATE)
    graph = build_agent_graph(dependencies)

    result = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message="VPN 无法连接，影响我的工作，请帮我创建工单。",
        ).model_dump(mode="json"),
        config={"configurable": {"thread_id": "ticket-intake-clarify-1"}},
    )
    state = AgentState.model_validate(result)

    assert "__interrupt__" not in result
    assert state.pending_action is None
    assert state.confirmation_status == ConfirmationStatus.NOT_REQUIRED
    assert "补充" in (state.answer or "")
    assert ticket_creation.states == []
