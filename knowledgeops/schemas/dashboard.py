"""Read models for the employee-facing operations dashboard."""

from pydantic import BaseModel, Field

from .conversation import AgentConversationSummaryRead
from .knowledge import KnowledgeBaseRead
from .ticket import TicketRead


class DashboardTicketSummary(BaseModel):
    """Counts for tickets created by the current employee."""

    open_count: int = Field(ge=0)
    in_progress_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    closed_count: int = Field(ge=0)


class DashboardIndexSummary(BaseModel):
    """Knowledge-base indexing health for the current workspace."""

    knowledge_base_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)


class DashboardRead(BaseModel):
    """A compact payload used to render the employee workbench."""

    actor: str
    tickets: DashboardTicketSummary
    indexing: DashboardIndexSummary
    recent_tickets: list[TicketRead] = Field(default_factory=list)
    knowledge_bases: list[KnowledgeBaseRead] = Field(default_factory=list)
    recent_conversations: list[AgentConversationSummaryRead] = Field(
        default_factory=list
    )
