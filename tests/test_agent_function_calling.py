import copy
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from langgraph.types import Command

from knowledgeops.agents.function_calling import (
    FUNCTION_DEFINITIONS,
    AgentFunctionCall,
    AgentModelResponse,
    OpenAIFunctionCallingAgent,
    TicketIntakeGuardedFunctionCallingAgent,
)
from knowledgeops.agents.state import AgentCitation, AgentIntent, AgentState, ConfirmationStatus
from knowledgeops.agents.workflow import AgentDependencies, build_agent_graph
from knowledgeops.models import TicketImpact, TicketPriority, TicketStatus
from knowledgeops.schemas import TicketRead


class FakeIntentRouter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def route(self, user_message: str) -> AgentIntent:
        self.calls.append(user_message)
        return AgentIntent.GENERAL_CHAT


class FakeKnowledgeSearchTool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.citation = AgentCitation(
            chunk_id="chunk-1",
            document_id="document-1",
            source_name="vpn-guide.md",
            source_type="markdown",
            chunk_index=0,
            start_char=0,
            end_char=20,
            text="VPN 连接需要使用企业账号。",
            score=0.9,
            sources=["vector"],
        )

    async def search(self, query: str, *, knowledge_base_id: str, limit: int = 5):
        self.calls.append((query, knowledge_base_id))
        return [self.citation]


class FakeChatAnswerGenerator:
    async def answer_general_chat(self, user_message, conversation_history) -> str:
        return "fallback"

    async def answer_from_citations(self, question, citations) -> str:
        return "fallback"


class FakeTicketQueryTool:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.ticket = TicketRead(
            id="ticket-1",
            title="VPN 无法连接",
            description="客户端报错 619。",
            priority=TicketPriority.HIGH,
            status=TicketStatus.IN_PROGRESS,
            requester="alice",
            category="network",
            impact=TicketImpact.SINGLE_USER,
            assignee="service-desk",
            created_at=now,
            updated_at=now,
        )
        self.list_calls: list[str] = []
        self.detail_calls: list[tuple[str, str]] = []

    async def list_tickets(self, *, actor: str, limit: int = 20):
        self.list_calls.append(actor)
        return [self.ticket]

    async def get_ticket(self, ticket_id: str, *, actor: str):
        self.detail_calls.append((ticket_id, actor))
        if ticket_id != self.ticket.id:
            raise LookupError(ticket_id)
        return self.ticket


class FakeTicketCreationTool:
    def __init__(self) -> None:
        self.states: list[AgentState] = []

    async def create_from_state(self, state: AgentState):
        self.states.append(state)
        return FakeTicketQueryTool().ticket


class FakeFunctionCallingAgent:
    def __init__(self, responses: list[AgentModelResponse]) -> None:
        self.responses = responses
        self.calls: list[list[dict[str, object]]] = []

    async def complete(self, messages, *, tool_choice: str = "auto") -> AgentModelResponse:
        self.calls.append(copy.deepcopy(messages))
        return self.responses.pop(0)


class FakeCompletions:
    def __init__(self, response) -> None:
        self.response = response
        self.last_request: dict[str, object] | None = None

    async def create(self, **kwargs):
        self.last_request = kwargs
        return self.response


def build_dependencies(responses: list[AgentModelResponse]):
    router = FakeIntentRouter()
    knowledge_search = FakeKnowledgeSearchTool()
    ticket_query = FakeTicketQueryTool()
    ticket_creation = FakeTicketCreationTool()
    function_agent = FakeFunctionCallingAgent(responses)
    dependencies = AgentDependencies(
        intent_router=router,
        knowledge_search=knowledge_search,
        chat_answer_generator=FakeChatAnswerGenerator(),
        ticket_query=ticket_query,
        ticket_creation=ticket_creation,
        function_calling_agent=function_agent,
    )
    return (
        dependencies,
        router,
        knowledge_search,
        ticket_query,
        ticket_creation,
        function_agent,
    )


@pytest.mark.asyncio
async def test_function_calling_executes_actor_scoped_ticket_tool_then_generates_answer():
    responses = [
        AgentModelResponse(
            content=None,
            tool_calls=[
                AgentFunctionCall(
                    id="call-1",
                    name="list_my_tickets",
                    arguments_json="{}",
                )
            ],
        ),
        AgentModelResponse(content="你的 VPN 工单正在处理中，由服务台跟进。", tool_calls=[]),
    ]
    dependencies, router, _, ticket_query, _, function_agent = build_dependencies(responses)
    graph = build_agent_graph(dependencies)

    result = await graph.ainvoke(
        AgentState(actor="alice", user_message="我的 VPN 工单处理到哪了？").model_dump(
            mode="json"
        ),
        config={"configurable": {"thread_id": "function-ticket-list-1"}},
    )
    state = AgentState.model_validate(result)

    assert state.answer == "你的 VPN 工单正在处理中，由服务台跟进。"
    assert state.ticket_ids == ["ticket-1"]
    assert ticket_query.list_calls == ["alice"]
    assert router.calls == []
    assert len(function_agent.calls) == 2
    assert function_agent.calls[0][-1] == {"role": "user", "content": "我的 VPN 工单处理到哪了？"}
    assert function_agent.calls[1][-2]["role"] == "assistant"
    assert function_agent.calls[1][-1]["role"] == "tool"
    tool_result = json.loads(function_agent.calls[1][-1]["content"])
    assert tool_result["tickets"][0]["id"] == "ticket-1"
    assert tool_result["tickets"][0]["assignee"] == "service-desk"


@pytest.mark.asyncio
async def test_function_calling_returns_knowledge_citations_to_the_final_answer():
    responses = [
        AgentModelResponse(
            content=None,
            tool_calls=[
                AgentFunctionCall(
                    id="call-knowledge",
                    name="search_knowledge_base",
                    arguments_json=json.dumps({"query": "VPN 连接方式"}),
                )
            ],
        ),
        AgentModelResponse(content="请使用企业账号登录 VPN。", tool_calls=[]),
    ]
    dependencies, _, knowledge_search, _, _, function_agent = build_dependencies(responses)
    graph = build_agent_graph(dependencies)

    result = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message="VPN 怎么连接？",
            knowledge_base_id="kb-1",
        ).model_dump(mode="json"),
        config={"configurable": {"thread_id": "function-knowledge-1"}},
    )
    state = AgentState.model_validate(result)

    assert state.answer == "请使用企业账号登录 VPN。"
    assert state.citations == [knowledge_search.citation]
    assert knowledge_search.calls == [("VPN 连接方式", "kb-1")]
    tool_result = json.loads(function_agent.calls[1][-1]["content"])
    assert tool_result["sources"][0]["source_name"] == "vpn-guide.md"


@pytest.mark.asyncio
async def test_function_calling_ticket_draft_still_requires_human_confirmation():
    responses = [
        AgentModelResponse(
            content=None,
            tool_calls=[
                AgentFunctionCall(
                    id="call-draft",
                    name="prepare_ticket_draft",
                    arguments_json=json.dumps(
                        {
                            "title": "VPN 无法连接",
                            "description": "客户端报错 619，影响本人远程办公。",
                            "priority": "high",
                            "category": "network",
                            "impact": "single_user",
                        }
                    ),
                )
            ],
        )
    ]
    dependencies, _, _, _, ticket_creation, _ = build_dependencies(responses)
    graph = build_agent_graph(dependencies)
    config = {"configurable": {"thread_id": "function-ticket-draft-1"}}

    interrupted = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message=(
                "VPN client shows error 619 on Windows 11 after restart, for 30 "
                "minutes, impact my remote work. Please create a support ticket."
            ),
        ).model_dump(
            mode="json"
        ),
        config=config,
    )

    assert "__interrupt__" in interrupted
    assert interrupted["confirmation_status"] == ConfirmationStatus.PENDING
    assert interrupted["pending_action"].arguments["priority"] == "high"
    assert ticket_creation.states == []

    completed = await graph.ainvoke(Command(resume=True), config=config)
    state = AgentState.model_validate(completed)
    assert state.created_ticket_id == "ticket-1"
    assert len(ticket_creation.states) == 1


@pytest.mark.asyncio
async def test_openai_function_agent_sends_declared_tools_and_parses_tool_calls():
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="list_my_tickets", arguments="{}"),
    )
    completions = FakeCompletions(
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=None, tool_calls=[tool_call])
                )
            ]
        )
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    agent = OpenAIFunctionCallingAgent(client=client, model="chat-test")

    response = await agent.complete([{"role": "user", "content": "查看我的工单"}])

    assert response.tool_calls == [
        AgentFunctionCall(id="call-1", name="list_my_tickets", arguments_json="{}")
    ]
    request = completions.last_request
    assert request is not None
    assert request["tools"] == FUNCTION_DEFINITIONS
    assert request["tool_choice"] == "auto"
    assert request["parallel_tool_calls"] is False


@pytest.mark.asyncio
async def test_ticket_intake_guard_asks_for_context_without_calling_the_model():
    delegate = FakeFunctionCallingAgent(
        [AgentModelResponse(content="unused", tool_calls=[])]
    )
    agent = TicketIntakeGuardedFunctionCallingAgent(delegate)

    response = await agent.complete(
        [
            {
                "role": "user",
                "content": "VPN connection failure 影响我的工作，请帮我创建支持工单。",
            }
        ]
    )

    assert response.tool_calls == []
    assert "补充" in (response.content or "")
    assert delegate.calls == []


@pytest.mark.asyncio
async def test_function_workflow_blocks_an_incomplete_ticket_before_tool_selection():
    responses = [
        AgentModelResponse(
            content=None,
            tool_calls=[
                AgentFunctionCall(
                    id="call-draft",
                    name="prepare_ticket_draft",
                    arguments_json=json.dumps(
                        {
                            "title": "VPN 无法连接",
                            "description": "虚构的模型补全内容。",
                            "priority": "high",
                            "category": "network",
                            "impact": "single_user",
                        }
                    ),
                )
            ],
        )
    ]
    dependencies, _, _, _, ticket_creation, function_agent = build_dependencies(responses)
    graph = build_agent_graph(dependencies)

    result = await graph.ainvoke(
        AgentState(
            actor="alice",
            user_message="VPN connection failure 影响我的工作，请帮我创建支持工单。",
        ).model_dump(mode="json"),
        config={"configurable": {"thread_id": "function-ticket-intake-1"}},
    )
    state = AgentState.model_validate(result)

    assert state.confirmation_status == ConfirmationStatus.NOT_REQUIRED
    assert state.pending_action is None
    assert "补充" in (state.answer or "")
    assert function_agent.calls == []
    assert ticket_creation.states == []
