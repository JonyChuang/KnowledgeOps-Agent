"""Database access for employee-owned Agent conversation history."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentConversation, AgentMessage
from ..models.base import utc_now


class AgentConversationRepository:
    """Store message history without owning the enclosing transaction."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, actor: str) -> AgentConversation:
        conversation = AgentConversation(actor=actor)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_for_actor(
        self,
        conversation_id: str,
        *,
        actor: str,
    ) -> AgentConversation | None:
        return await self.session.scalar(
            select(AgentConversation).where(
                AgentConversation.id == conversation_id,
                AgentConversation.actor == actor,
            )
        )

    async def list_for_actor(
        self,
        *,
        actor: str,
        limit: int,
    ) -> list[AgentConversation]:
        result = await self.session.scalars(
            select(AgentConversation)
            .where(AgentConversation.actor == actor)
            .order_by(AgentConversation.updated_at.desc())
            .limit(limit)
        )
        return list(result)

    async def list_messages(
        self,
        conversation_id: str,
    ) -> list[AgentMessage]:
        result = await self.session.scalars(
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation_id)
            .order_by(AgentMessage.sequence)
        )
        return list(result)

    async def get_latest_message(
        self,
        conversation_id: str,
    ) -> AgentMessage | None:
        return await self.session.scalar(
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation_id)
            .order_by(AgentMessage.sequence.desc())
            .limit(1)
        )

    async def count_messages(self, conversation_id: str) -> int:
        count = await self.session.scalar(
            select(func.count(AgentMessage.id)).where(
                AgentMessage.conversation_id == conversation_id
            )
        )
        return count or 0

    async def append_message(
        self,
        conversation: AgentConversation,
        *,
        role: str,
        content: str | None,
        turn_id: str | None = None,
        turn_status: str | None = None,
        citations: list[dict[str, object]] | None = None,
        pending_action: dict[str, object] | None = None,
        created_ticket_id: str | None = None,
        ticket_ids: list[str] | None = None,
        error: str | None = None,
    ) -> AgentMessage:
        sequence = await self.count_messages(conversation.id)
        message = AgentMessage(
            conversation_id=conversation.id,
            sequence=sequence,
            role=role,
            content=content,
            turn_id=turn_id,
            turn_status=turn_status,
            citations=citations or [],
            pending_action=pending_action,
            created_ticket_id=created_ticket_id,
            ticket_ids=ticket_ids or [],
            error=error,
        )
        self.session.add(message)
        conversation.updated_at = utc_now()
        await self.session.flush()
        return message

    async def get_message_for_turn(
        self,
        turn_id: str,
        *,
        actor: str,
    ) -> AgentMessage | None:
        return await self.session.scalar(
            select(AgentMessage)
            .join(AgentConversation)
            .where(
                AgentMessage.turn_id == turn_id,
                AgentConversation.actor == actor,
            )
        )

    async def update_turn(
        self,
        message: AgentMessage,
        *,
        content: str | None,
        turn_status: str,
        citations: list[dict[str, object]],
        pending_action: dict[str, object] | None,
        created_ticket_id: str | None,
        ticket_ids: list[str],
        error: str | None,
    ) -> AgentMessage:
        message.content = content
        message.turn_status = turn_status
        message.citations = citations
        message.pending_action = pending_action
        message.created_ticket_id = created_ticket_id
        message.ticket_ids = ticket_ids
        message.error = error
        conversation = await self.session.get(
            AgentConversation,
            message.conversation_id,
        )
        if conversation is not None:
            conversation.updated_at = utc_now()
        await self.session.flush()
        return message
