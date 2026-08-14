"""HTTP response contracts for persistent Agent conversation history."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .agent import AgentCitationRead, AgentPendingActionRead


class AgentConversationMessageRead(BaseModel):
    id: str
    role: Literal["user", "agent"]
    content: str | None = None
    thread_id: str | None = None
    status: Literal[
        "completed",
        "confirmation_required",
        "cancelled",
        "failed",
    ] | None = None
    citations: list[AgentCitationRead] = Field(default_factory=list)
    pending_action: AgentPendingActionRead | None = None
    created_ticket_id: str | None = None
    ticket_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime


class AgentConversationSummaryRead(BaseModel):
    id: str
    title: str
    updated_at: datetime
    message_count: int = Field(ge=0)
    last_message_preview: str = ""


class AgentConversationRead(AgentConversationSummaryRead):
    actor: str
    knowledge_base_id: str | None = None
    messages: list[AgentConversationMessageRead] = Field(default_factory=list)


class AgentConversationListRead(BaseModel):
    items: list[AgentConversationSummaryRead] = Field(default_factory=list)
