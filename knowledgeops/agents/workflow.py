"""LangGraph workflow for KnowledgeOps Agent requests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .chat import ChatAnswerGenerator
from .function_calling import (
    AgentFunctionCall,
    FunctionCallingAgent,
    build_function_call_messages,
)
from .router import IntentRouter
from .state import (
    AgentIntent,
    AgentState,
    ConfirmationStatus,
    PendingAction,
)
from .ticket_intake import assess_ticket_intake
from .ticket_tools import TicketCreationTool, TicketQueryTool
from .tools import KnowledgeBaseScopeTool, KnowledgeSearchTool


@dataclass(frozen=True)
class AgentDependencies:
    """Runtime tools injected into a graph without entering AgentState."""

    intent_router: IntentRouter
    knowledge_search: KnowledgeSearchTool
    chat_answer_generator: ChatAnswerGenerator
    ticket_query: TicketQueryTool
    ticket_creation: TicketCreationTool
    knowledge_base_scope: KnowledgeBaseScopeTool | None = None
    function_calling_agent: FunctionCallingAgent | None = None


def ticket_summary(ticket: Any) -> dict[str, object]:
    """Expose only the employee-visible ticket fields to the model."""
    return {
        "id": ticket.id,
        "title": ticket.title,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "category": ticket.category,
        "impact": ticket.impact.value,
        "assignee": ticket.assignee,
        "updated_at": ticket.updated_at.isoformat(),
    }


def ticket_detail(ticket: Any) -> dict[str, object]:
    """Return an actor-scoped ticket as structured function output."""
    return {
        **ticket_summary(ticket),
        "description": ticket.description,
        "requester": ticket.requester,
        "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None,
    }


def ticket_draft_from_arguments(arguments: dict[str, object]) -> PendingAction:
    """Validate model arguments before they enter the human approval state."""
    title = str(arguments.get("title", "")).strip()
    description = str(arguments.get("description", "")).strip()
    priority = str(arguments.get("priority", "")).strip()
    category = str(arguments.get("category", "")).strip()
    impact = str(arguments.get("impact", "")).strip()
    if not title or not description or not priority or not category or not impact:
        raise ValueError("工单草稿缺少必要字段，请补充问题描述后重试。")
    if len(title) < 2 or len(title) > 200:
        raise ValueError("工单标题长度应为 2 到 200 个字符。")
    if len(description) > 20_000:
        raise ValueError("工单描述不能超过 20000 个字符。")
    if priority not in {"low", "medium", "high", "urgent"}:
        raise ValueError("工单优先级无效。")
    if impact not in {"single_user", "team", "department", "company"}:
        raise ValueError("工单影响范围无效。")
    if len(category) < 2 or len(category) > 80:
        raise ValueError("工单分类长度应为 2 到 80 个字符。")
    return PendingAction(
        action_type="ticket.create",
        arguments={
            "title": title,
            "description": description,
            "priority": priority,
            "category": category,
            "impact": impact,
        },
    )


def build_agent_graph(
    dependencies: AgentDependencies,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Build one Agent graph with injected runtime dependencies."""

    async def route_message(state: AgentState) -> dict[str, object]:
        if dependencies.function_calling_agent is not None:
            return {"intent": AgentIntent.GENERAL_CHAT}
        intent = await dependencies.intent_router.route(state.user_message)
        if intent is None:
            return {"error": "无法判断请求类型，请明确说明需求。"}

        return {"intent": intent}

    async def answer_general_chat(
        state: AgentState,
    ) -> dict[str, object]:
        """Run the model-selected tools, then let the model write the final answer."""
        if dependencies.function_calling_agent is not None:
            return await answer_with_function_calls(state)
        try:
            answer = await dependencies.chat_answer_generator.answer_general_chat(
                state.user_message,
                state.conversation_history,
            )
        except Exception:  # noqa: BLE001 - external model errors must not fail the Agent turn
            return {
                "error": (
                    "Chat 模型暂时无法生成回复。请检查 CHAT_MODEL、CHAT_BASE_URL、"
                    "CHAT_API_KEY 及模型服务连接。"
                )
            }
        return {"answer": answer}

    async def answer_with_function_calls(state: AgentState) -> dict[str, object]:
        intake = assess_ticket_intake(_ticket_intake_messages(state))
        if intake.requires_clarification:
            return {"answer": intake.clarification_message}

        messages = build_function_call_messages(
            user_message=state.user_message,
            conversation_history=state.conversation_history,
        )
        citations = []
        ticket_ids: list[str] = []
        # A bound prevents a misconfigured model from creating an endless tool loop.
        for _ in range(3):
            try:
                response = await dependencies.function_calling_agent.complete(messages)
            except Exception:  # noqa: BLE001 - provider errors must not crash a turn
                return {
                    "error": (
                        "Chat 模型暂时无法生成回复。请检查 CHAT_MODEL、CHAT_BASE_URL、"
                        "CHAT_API_KEY、模型服务连接及 Function Calling 支持。"
                    )
                }

            if not response.tool_calls:
                if response.content and response.content.strip():
                    return {
                        "answer": response.content.strip(),
                        "citations": citations,
                        "ticket_ids": ticket_ids,
                    }
                return {"error": "Chat 模型返回了空回复。"}

            messages.append(response.as_assistant_message())
            for call in response.tool_calls:
                result, new_citations, new_ticket_ids, pending_action = (
                    await execute_function_call(call, state)
                )
                citations.extend(new_citations)
                ticket_ids.extend(new_ticket_ids)
                if pending_action is not None:
                    return {
                        "intent": AgentIntent.TICKET_CREATE,
                        "pending_action": pending_action,
                        "confirmation_status": ConfirmationStatus.PENDING,
                        "citations": citations,
                        "ticket_ids": ticket_ids,
                    }
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        return {"error": "工具调用次数超过安全上限，请换一种方式描述需求。"}

    async def execute_function_call(
        call: AgentFunctionCall,
        state: AgentState,
    ) -> tuple[
        dict[str, object],
        list,
        list[str],
        PendingAction | None,
    ]:
        """Execute only the allow-listed, actor-scoped tools selected by the model."""
        try:
            arguments = call.arguments
        except (TypeError, ValueError, json.JSONDecodeError):
            return ({"error": "工具参数不是有效 JSON。"}, [], [], None)

        if call.name == "search_knowledge_base":
            query = str(arguments.get("query", "")).strip()
            if not query:
                return ({"error": "知识库查询缺少 query。"}, [], [], None)
            if not state.knowledge_base_id:
                return (
                    {"error": "当前没有选择知识库，无法查询内部资料。"},
                    [],
                    [],
                    None,
                )
            found = await dependencies.knowledge_search.search(
                query,
                knowledge_base_id=state.knowledge_base_id,
            )
            return (
                {
                    "query": query,
                    "sources": [
                        {
                            "source_name": citation.source_name,
                            "text": citation.text,
                        }
                        for citation in found
                    ],
                },
                found,
                [],
                None,
            )

        if call.name == "list_my_tickets":
            tickets = await dependencies.ticket_query.list_tickets(actor=state.actor)
            return (
                {
                    "tickets": [ticket_summary(ticket) for ticket in tickets],
                    "total": len(tickets),
                },
                [],
                [ticket.id for ticket in tickets],
                None,
            )

        if call.name == "get_my_ticket_detail":
            ticket_id = str(arguments.get("ticket_id", "")).strip()
            if not ticket_id:
                return ({"error": "工单查询缺少 ticket_id。"}, [], [], None)
            try:
                ticket = await dependencies.ticket_query.get_ticket(
                    ticket_id,
                    actor=state.actor,
                )
            except Exception:  # noqa: BLE001 - hide non-owned ticket existence
                return ({"error": "没有找到你的这张工单。"}, [], [], None)
            return ({"ticket": ticket_detail(ticket)}, [], [ticket.id], None)

        if call.name == "prepare_ticket_draft":
            intake = assess_ticket_intake(_ticket_intake_messages(state))
            if intake.requires_clarification:
                return ({"error": intake.clarification_message}, [], [], None)
            try:
                pending_action = ticket_draft_from_arguments(arguments)
            except ValueError as error:
                return ({"error": str(error)}, [], [], None)
            return (
                {
                    "draft": pending_action.arguments,
                    "confirmation_required": True,
                    "message": "工单草稿已准备，等待员工确认后才会创建。",
                },
                [],
                [],
                pending_action,
            )

        return ({"error": f"不允许调用工具：{call.name}"}, [], [], None)

    async def answer_knowledge_question(
        state: AgentState,
    ) -> dict[str, object]:
        if not state.knowledge_base_id:
            return {"error": "知识库问答需要 knowledge_base_id。"}

        citations = await dependencies.knowledge_search.search(
            state.user_message,
            knowledge_base_id=state.knowledge_base_id,
        )
        if not citations:
            if dependencies.knowledge_base_scope is not None:
                scope_citations = (
                    await dependencies.knowledge_base_scope.list_ready_citations(
                        knowledge_base_id=state.knowledge_base_id,
                    )
                )
                if scope_citations:
                    source_names = "、".join(
                        dict.fromkeys(
                            citation.source_name
                            for citation in scope_citations
                        )
                    )
                    return {
                        "answer": (
                            f"知识库中没有足够信息回答“{state.user_message}”。"
                            f"当前已索引资料主要包括 {source_names}，"
                            "现有内容未覆盖所问主题。请补充相关资料后再查询。"
                        ),
                        "citations": scope_citations,
                    }
            return {
                "answer": "知识库中没有找到相关信息。",
                "citations": [],
            }

        try:
            answer = await dependencies.chat_answer_generator.answer_from_citations(
                state.user_message,
                citations,
            )
        except Exception:  # noqa: BLE001 - preserve citations when generation fails
            return {
                "error": "知识库检索完成，但 Chat 模型生成回答失败。",
                "citations": citations,
            }
        return {
            "answer": answer,
            "citations": citations,
        }

    async def query_tickets(state: AgentState) -> dict[str, object]:
        tickets = await dependencies.ticket_query.list_tickets(
            actor=state.actor,
        )
        if not tickets:
            return {
                "answer": "没有找到你的工单。",
                "ticket_ids": [],
            }

        status_labels = {
            "open": "待受理",
            "in_progress": "处理中",
            "awaiting_requester": "待你补充",
            "resolved": "已解决",
            "closed": "已关闭",
        }
        priority_labels = {
            "low": "低",
            "medium": "中",
            "high": "高",
            "urgent": "紧急",
        }
        summary = "\n".join(
            (
                f"{index}. {ticket.title}｜"
                f"{status_labels.get(ticket.status.value, ticket.status.value)}｜"
                f"{priority_labels.get(ticket.priority.value, ticket.priority.value)}优先级"
                f"｜处理人：{ticket.assignee or '暂未分配'}"
            )
            for index, ticket in enumerate(tickets, start=1)
        )
        return {
            "answer": f"你当前共有 {len(tickets)} 张工单：\n{summary}",
            "ticket_ids": [ticket.id for ticket in tickets],
        }

    async def prepare_ticket(state: AgentState) -> dict[str, object]:
        intake = assess_ticket_intake(_ticket_intake_messages(state))
        if intake.requires_clarification:
            return {"answer": intake.clarification_message}
        message = state.user_message.strip()
        return {
            "pending_action": PendingAction(
                action_type="ticket.create",
                arguments={
                    "title": message[:200],
                    "description": message,
                },
            ),
            "confirmation_status": ConfirmationStatus.PENDING,
        }

    def confirm_ticket(state: AgentState) -> dict[str, object]:
        decision = interrupt(
            {
                "action": "ticket.create",
                "arguments": state.pending_action.arguments
                if state.pending_action
                else {},
            }
        )

        if decision is True:
            return {
                "confirmation_status": ConfirmationStatus.CONFIRMED,
            }

        return {
            "confirmation_status": ConfirmationStatus.REJECTED,
            "answer": "已取消创建工单。",
        }

    async def create_ticket(state: AgentState) -> dict[str, object]:
        ticket = await dependencies.ticket_creation.create_from_state(state)
        return {
            "created_ticket_id": ticket.id,
            "ticket_ids": [ticket.id],
            "answer": f"工单已创建：{ticket.id}",
        }

    def choose_route(state: AgentState) -> str:
        if state.error:
            return "end"

        if state.intent == AgentIntent.GENERAL_CHAT:
            return "general_chat"
        if state.intent == AgentIntent.KNOWLEDGE_QA:
            return "knowledge_qa"
        if state.intent == AgentIntent.TICKET_QUERY:
            return "ticket_query"
        if state.intent == AgentIntent.TICKET_CREATE:
            return "prepare_ticket"

        return "end"

    def choose_after_confirmation(state: AgentState) -> str:
        if state.confirmation_status == ConfirmationStatus.CONFIRMED:
            return "create_ticket"

        return "end"

    def choose_after_ticket_preparation(state: AgentState) -> str:
        if (
            state.pending_action is not None
            and state.confirmation_status == ConfirmationStatus.PENDING
        ):
            return "confirm_ticket"
        return "end"

    def choose_after_function_calling(state: AgentState) -> str:
        if state.confirmation_status == ConfirmationStatus.PENDING:
            return "confirm_ticket"
        return "end"

    graph = StateGraph(AgentState)
    graph.add_node("route", route_message)
    graph.add_node("general_chat", answer_general_chat)
    graph.add_node("knowledge_qa", answer_knowledge_question)
    graph.add_node("ticket_query", query_tickets)
    graph.add_node("prepare_ticket", prepare_ticket)
    graph.add_node("confirm_ticket", confirm_ticket)
    graph.add_node("create_ticket", create_ticket)

    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        choose_route,
        {
            "general_chat": "general_chat",
            "knowledge_qa": "knowledge_qa",
            "ticket_query": "ticket_query",
            "prepare_ticket": "prepare_ticket",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "general_chat",
        choose_after_function_calling,
        {
            "confirm_ticket": "confirm_ticket",
            "end": END,
        },
    )
    graph.add_edge("knowledge_qa", END)
    graph.add_edge("ticket_query", END)
    graph.add_conditional_edges(
        "prepare_ticket",
        choose_after_ticket_preparation,
        {
            "confirm_ticket": "confirm_ticket",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "confirm_ticket",
        choose_after_confirmation,
        {
            "create_ticket": "create_ticket",
            "end": END,
        },
    )
    graph.add_edge("create_ticket", END)

    active_checkpointer = (
        checkpointer if checkpointer is not None else MemorySaver()
    )
    return graph.compile(checkpointer=active_checkpointer)


def _ticket_intake_messages(state: AgentState) -> list[str]:
    """Use employee turns only; assistant text must not supply ticket facts."""
    return [
        *(message.content for message in state.conversation_history if message.role == "user"),
        state.user_message,
    ]
