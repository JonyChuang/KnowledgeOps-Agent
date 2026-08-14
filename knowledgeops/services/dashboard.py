"""Read-only aggregation for the employee workbench."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentConversation, AgentMessage, DocumentStatus, KnowledgeBase, Ticket, TicketStatus
from ..repositories import (
    AgentConversationRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
    TicketRepository,
)


@dataclass(frozen=True)
class DashboardConversationSummary:
    """The small conversation slice shown on the employee workbench."""

    conversation: AgentConversation
    message_count: int
    last_message_preview: str


@dataclass(frozen=True)
class DashboardSnapshot:
    """Business data consumed by the dashboard HTTP endpoint."""

    actor: str
    ticket_counts: dict[TicketStatus, int]
    document_counts: dict[DocumentStatus, int]
    recent_tickets: list[Ticket]
    knowledge_bases: list[KnowledgeBase]
    knowledge_base_count: int
    recent_conversations: list[DashboardConversationSummary]


class DashboardService:
    """Compose dashboard data without creating another source of truth."""

    def __init__(self, session: AsyncSession) -> None:
        self.tickets = TicketRepository(session)
        self.documents = DocumentRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.conversations = AgentConversationRepository(session)

    async def get_snapshot(self, *, actor: str) -> DashboardSnapshot:
        """Load employee tickets and shared indexing health.

        This first version intentionally reuses the existing shared
        knowledge-base scope. A later authorization phase will replace that
        scope with workspace membership checks before production use.
        """
        ticket_counts = await self.tickets.count_for_requester_by_status(
            requester=actor
        )
        recent_tickets = await self.tickets.list_for_requester(
            requester=actor,
            limit=5,
        )
        document_counts = await self.documents.count_by_status()
        knowledge_bases = await self.knowledge_bases.list()
        conversations = await self.conversations.list_for_actor(
            actor=actor,
            limit=3,
        )
        recent_conversations = []
        for conversation in conversations:
            messages = await self.conversations.list_messages(conversation.id)
            last_message: AgentMessage | None = messages[-1] if messages else None
            recent_conversations.append(
                DashboardConversationSummary(
                    conversation=conversation,
                    message_count=len(messages),
                    last_message_preview=(
                        (last_message.content or last_message.error or "等待输入消息")
                        if last_message is not None
                        else "等待输入消息"
                    ),
                )
            )
        return DashboardSnapshot(
            actor=actor,
            ticket_counts=ticket_counts,
            document_counts=document_counts,
            recent_tickets=recent_tickets,
            knowledge_bases=knowledge_bases[:4],
            knowledge_base_count=len(knowledge_bases),
            recent_conversations=recent_conversations,
        )
