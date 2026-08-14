"""Business operations for durable, employee-owned Agent conversations."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentConversation, AgentMessage
from ..repositories import AgentConversationRepository
from .knowledge import ResourceNotFoundError


@dataclass(frozen=True)
class ConversationWithMessages:
    conversation: AgentConversation
    messages: list[AgentMessage]


class ConversationService:
    """Persist and retrieve conversation state independently of the Agent graph."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversations = AgentConversationRepository(session)

    async def create_conversation(self, *, actor: str) -> AgentConversation:
        conversation = await self.conversations.create(actor=actor)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def list_conversations(
        self,
        *,
        actor: str,
        limit: int = 20,
    ) -> list[AgentConversation]:
        return await self.conversations.list_for_actor(actor=actor, limit=limit)

    async def get_conversation(
        self,
        conversation_id: str,
        *,
        actor: str,
    ) -> ConversationWithMessages:
        conversation = await self._require_conversation(conversation_id, actor=actor)
        messages = await self.conversations.list_messages(conversation.id)
        return ConversationWithMessages(conversation=conversation, messages=messages)

    async def record_user_message(
        self,
        conversation_id: str,
        *,
        actor: str,
        content: str,
        knowledge_base_id: str | None,
    ) -> AgentConversation:
        conversation = await self._require_conversation(conversation_id, actor=actor)
        await self.conversations.append_message(
            conversation,
            role="user",
            content=content,
        )
        if conversation.title == "新对话":
            conversation.title = self._title_from_message(content)
        if knowledge_base_id:
            conversation.knowledge_base_id = knowledge_base_id
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def record_turn(
        self,
        conversation_id: str,
        *,
        actor: str,
        turn_id: str,
        answer: str | None,
        turn_status: str,
        citations: list[dict[str, object]],
        pending_action: dict[str, object] | None,
        created_ticket_id: str | None,
        ticket_ids: list[str],
        error: str | None,
    ) -> AgentMessage:
        conversation = await self._require_conversation(conversation_id, actor=actor)
        message = await self.conversations.append_message(
            conversation,
            role="agent",
            content=answer,
            turn_id=turn_id,
            turn_status=turn_status,
            citations=citations,
            pending_action=pending_action,
            created_ticket_id=created_ticket_id,
            ticket_ids=ticket_ids,
            error=error,
        )
        await self.session.commit()
        return message

    async def update_turn(
        self,
        turn_id: str,
        *,
        actor: str,
        answer: str | None,
        turn_status: str,
        citations: list[dict[str, object]],
        pending_action: dict[str, object] | None,
        created_ticket_id: str | None,
        ticket_ids: list[str],
        error: str | None,
    ) -> AgentMessage:
        message = await self.conversations.get_message_for_turn(turn_id, actor=actor)
        if message is None:
            raise ResourceNotFoundError("Agent conversation not found.")
        message = await self.conversations.update_turn(
            message,
            content=answer,
            turn_status=turn_status,
            citations=citations,
            pending_action=pending_action,
            created_ticket_id=created_ticket_id,
            ticket_ids=ticket_ids,
            error=error,
        )
        await self.session.commit()
        return message

    async def _require_conversation(
        self,
        conversation_id: str,
        *,
        actor: str,
    ) -> AgentConversation:
        conversation = await self.conversations.get_for_actor(
            conversation_id,
            actor=actor,
        )
        if conversation is None:
            raise ResourceNotFoundError("Agent conversation not found.")
        return conversation

    @staticmethod
    def _title_from_message(content: str) -> str:
        normalized = " ".join(content.split())
        return normalized[:18] + ("..." if len(normalized) > 18 else "")
