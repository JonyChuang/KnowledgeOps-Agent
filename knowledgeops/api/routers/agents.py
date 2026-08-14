from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from ...agents import (
    AgentConversationMessage,
    AgentState,
    ConfirmationStatus,
    build_agent_graph,
)
from ...schemas import (
    AgentCitationRead,
    AgentConfirmationCreate,
    AgentConversationListRead,
    AgentConversationMessageRead,
    AgentConversationRead,
    AgentConversationSummaryRead,
    AgentPendingActionRead,
    AgentTurnCreate,
    AgentTurnRead,
)
from ...services import ConversationService, ResourceNotFoundError
from ...tasks import build_agent_runtime
from ..dependencies import get_actor, get_session

agent_router = APIRouter(prefix="/agent", tags=["agent"])


def _graph_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _response_from_result(
    thread_id: str,
    result: dict[str, Any],
    *,
    conversation_id: str | None = None,
) -> AgentTurnRead:
    state = AgentState.model_validate(result)

    if "__interrupt__" in result:
        turn_status = "confirmation_required"
    elif state.confirmation_status == ConfirmationStatus.REJECTED:
        turn_status = "cancelled"
    elif state.error is not None:
        turn_status = "failed"
    else:
        turn_status = "completed"

    pending_action = None
    if turn_status == "confirmation_required":
        pending_action = AgentPendingActionRead.model_validate(
            state.pending_action.model_dump()
        )

    return AgentTurnRead(
        thread_id=thread_id,
        conversation_id=conversation_id,
        status=turn_status,
        answer=state.answer,
        citations=[
            AgentCitationRead.model_validate(citation.model_dump())
            for citation in state.citations
        ],
        pending_action=pending_action,
        created_ticket_id=state.created_ticket_id,
        ticket_ids=state.ticket_ids,
        error=state.error,
    )


def _turn_storage_values(turn: AgentTurnRead) -> dict[str, object]:
    """Map the public turn model to the durable conversation record."""
    return {
        "answer": turn.answer,
        "turn_status": turn.status,
        "citations": [citation.model_dump(mode="json") for citation in turn.citations],
        "pending_action": (
            turn.pending_action.model_dump(mode="json")
            if turn.pending_action is not None
            else None
        ),
        "created_ticket_id": turn.created_ticket_id,
        "ticket_ids": turn.ticket_ids,
        "error": turn.error,
    }


def _conversation_history(stored_messages) -> list[AgentConversationMessage]:
    """Bound model context to recent user/Agent messages, excluding empty turns."""
    history: list[AgentConversationMessage] = []
    for message in stored_messages[-8:]:
        content = (message.content or message.error or "").strip()
        if not content:
            continue
        history.append(
            AgentConversationMessage(
                role="assistant" if message.role == "agent" else "user",
                content=content[:1_500],
            )
        )
    return history


def _message_read(message) -> AgentConversationMessageRead:
    pending_action = (
        AgentPendingActionRead.model_validate(message.pending_action)
        if message.pending_action is not None
        else None
    )
    return AgentConversationMessageRead(
        id=message.id,
        role=message.role,
        content=message.content,
        thread_id=message.turn_id,
        status=message.turn_status,
        citations=[
            AgentCitationRead.model_validate(citation)
            for citation in message.citations
        ],
        pending_action=pending_action,
        created_ticket_id=message.created_ticket_id,
        ticket_ids=message.ticket_ids,
        error=message.error,
        created_at=message.created_at,
    )


def _summary_read(conversation, *, message_count: int, last_preview: str) -> AgentConversationSummaryRead:
    return AgentConversationSummaryRead(
        id=conversation.id,
        title=conversation.title,
        updated_at=conversation.updated_at,
        message_count=message_count,
        last_message_preview=last_preview,
    )


@agent_router.get("/conversations", response_model=AgentConversationListRead)
async def list_agent_conversations(
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> AgentConversationListRead:
    """List the current employee's recent conversation summaries."""
    service = ConversationService(session)
    conversations = await service.list_conversations(actor=actor)
    items = []
    for conversation in conversations:
        messages = await service.conversations.list_messages(conversation.id)
        last_message = messages[-1] if messages else None
        preview = (
            last_message.content or last_message.error or "等待输入消息"
            if last_message is not None
            else "等待输入消息"
        )
        items.append(
            _summary_read(
                conversation,
                message_count=len(messages),
                last_preview=preview,
            )
        )
    return AgentConversationListRead(items=items)


@agent_router.get(
    "/conversations/{conversation_id}",
    response_model=AgentConversationRead,
)
async def get_agent_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> AgentConversationRead:
    """Return one employee-owned conversation with its complete messages."""
    try:
        stored = await ConversationService(session).get_conversation(
            conversation_id,
            actor=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    messages = [_message_read(message) for message in stored.messages]
    last_message = messages[-1] if messages else None
    preview = (
        last_message.content or last_message.error or "等待输入消息"
        if last_message is not None
        else "等待输入消息"
    )
    return AgentConversationRead(
        **_summary_read(
            stored.conversation,
            message_count=len(messages),
            last_preview=preview,
        ).model_dump(),
        actor=stored.conversation.actor,
        knowledge_base_id=stored.conversation.knowledge_base_id,
        messages=messages,
    )


@agent_router.post(
    "/turns",
    response_model=AgentTurnRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_turn(
    payload: AgentTurnCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> AgentTurnRead:
    thread_id = str(uuid4())
    config = _graph_config(thread_id)
    conversation_service = ConversationService(session)
    if payload.conversation_id is None:
        conversation = await conversation_service.create_conversation(actor=actor)
        conversation_history: list[AgentConversationMessage] = []
    else:
        try:
            conversation = await conversation_service.get_conversation(
                payload.conversation_id,
                actor=actor,
            )
        except ResourceNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        conversation_history = _conversation_history(conversation.messages)
        conversation = conversation.conversation

    await conversation_service.record_user_message(
        conversation.id,
        actor=actor,
        content=payload.user_message,
        knowledge_base_id=payload.knowledge_base_id,
    )
    runtime = build_agent_runtime(
        session,
        request.app.state.settings,
    )

    try:
        graph = build_agent_graph(
            runtime.dependencies,
            checkpointer=request.app.state.agent_checkpointer,
        )
        result = await graph.ainvoke(
            AgentState(
                actor=actor,
                user_message=payload.user_message,
                knowledge_base_id=payload.knowledge_base_id,
                conversation_history=conversation_history,
            ).model_dump(mode="json"),
            config=config,
        )
        turn = _response_from_result(
            thread_id,
            result,
            conversation_id=conversation.id,
        )
        await conversation_service.record_turn(
            conversation.id,
            actor=actor,
            turn_id=thread_id,
            **_turn_storage_values(turn),
        )
        return turn
    finally:
        await runtime.close()


@agent_router.post(
    "/turns/{thread_id}/confirmation",
    response_model=AgentTurnRead,
)
async def confirm_agent_turn(
    thread_id: str,
    payload: AgentConfirmationCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> AgentTurnRead:
    config = _graph_config(thread_id)
    runtime = build_agent_runtime(
        session,
        request.app.state.settings,
    )

    try:
        graph = build_agent_graph(
            runtime.dependencies,
            checkpointer=request.app.state.agent_checkpointer,
        )
        snapshot = await graph.aget_state(config)

        if not snapshot.values:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent conversation not found.",
            )

        saved_state = AgentState.model_validate(snapshot.values)
        if saved_state.actor != actor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent conversation not found.",
            )

        if saved_state.confirmation_status != ConfirmationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent conversation has no pending confirmation.",
            )

        result = await graph.ainvoke(
            Command(resume=payload.approved),
            config=config,
        )
        turn = _response_from_result(thread_id, result)
        try:
            stored_message = await ConversationService(session).update_turn(
                thread_id,
                actor=actor,
                **_turn_storage_values(turn),
            )
        except ResourceNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        turn.conversation_id = stored_message.conversation_id
        return turn
    finally:
        await runtime.close()
