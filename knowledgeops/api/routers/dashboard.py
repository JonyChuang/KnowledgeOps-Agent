"""Employee workbench endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import DocumentStatus, TicketStatus
from ...schemas import (
    AgentConversationSummaryRead,
    DashboardIndexSummary,
    DashboardRead,
    DashboardTicketSummary,
    KnowledgeBaseRead,
    TicketRead,
)
from ...services import DashboardService
from ..dependencies import get_actor, get_session

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@dashboard_router.get("", response_model=DashboardRead)
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> DashboardRead:
    """Return the current employee's compact operational workbench."""
    snapshot = await DashboardService(session).get_snapshot(actor=actor)
    ticket_counts = snapshot.ticket_counts
    document_counts = snapshot.document_counts

    return DashboardRead(
        actor=snapshot.actor,
        tickets=DashboardTicketSummary(
            open_count=ticket_counts.get(TicketStatus.OPEN, 0),
            in_progress_count=ticket_counts.get(TicketStatus.IN_PROGRESS, 0),
            resolved_count=ticket_counts.get(TicketStatus.RESOLVED, 0),
            closed_count=ticket_counts.get(TicketStatus.CLOSED, 0),
        ),
        indexing=DashboardIndexSummary(
            knowledge_base_count=snapshot.knowledge_base_count,
            document_count=sum(document_counts.values()),
            ready_count=document_counts.get(DocumentStatus.READY, 0),
            pending_count=(
                document_counts.get(DocumentStatus.UPLOADED, 0)
                + document_counts.get(DocumentStatus.INDEXING, 0)
            ),
            failed_count=document_counts.get(DocumentStatus.FAILED, 0),
        ),
        recent_tickets=[
            TicketRead.model_validate(ticket) for ticket in snapshot.recent_tickets
        ],
        knowledge_bases=[
            KnowledgeBaseRead.model_validate(knowledge_base)
            for knowledge_base in snapshot.knowledge_bases
        ],
        recent_conversations=[
            AgentConversationSummaryRead(
                id=item.conversation.id,
                title=item.conversation.title,
                updated_at=item.conversation.updated_at,
                message_count=item.message_count,
                last_message_preview=item.last_message_preview,
            )
            for item in snapshot.recent_conversations
        ],
    )
