"""Serializable state contracts for the KnowledgeOps Agent workflow."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AgentIntent(str, Enum):
    """The supported routes in the enterprise assistant workflow."""

    GENERAL_CHAT = "general_chat"
    KNOWLEDGE_QA = "knowledge_qa"
    TICKET_QUERY = "ticket_query"
    TICKET_CREATE = "ticket_create"


class ConfirmationStatus(str, Enum):
    """Confirmation state for a pending write action."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class AgentCitation(BaseModel):
    """Serializable citation copied from a retrieved knowledge chunk."""

    chunk_id: str
    document_id: str
    source_name: str
    source_type: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str
    score: float
    sources: list[str] = Field(default_factory=list)
    rerank_score: float | None = None


class AgentConversationMessage(BaseModel):
    """One bounded, previously persisted message supplied to the Chat model."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1_500)


class PendingAction(BaseModel):
    """A write action prepared by the Agent but not yet executed."""

    action_type: Literal["ticket.create"]
    arguments: dict[str, str] = Field(default_factory=dict)


class AgentState(BaseModel):
    """Data passed between workflow nodes without runtime clients or sessions."""

    actor: str = Field(min_length=1, max_length=120)
    user_message: str = Field(min_length=1, max_length=4_000)
    knowledge_base_id: str | None = None
    conversation_history: list[AgentConversationMessage] = Field(default_factory=list)
    intent: AgentIntent | None = None
    answer: str | None = None
    citations: list[AgentCitation] = Field(default_factory=list)
    pending_action: PendingAction | None = None
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NOT_REQUIRED
    created_ticket_id: str | None = None
    ticket_ids: list[str] = Field(default_factory=list)
    error: str | None = None

    @property
    def can_create_ticket(self) -> bool:
        """Allow the write node to run only after explicit confirmation."""
        return (
            self.intent == AgentIntent.TICKET_CREATE
            and self.pending_action is not None
            and self.confirmation_status == ConfirmationStatus.CONFIRMED
        )

    @model_validator(mode="after")
    def validate_write_state(self) -> AgentState:
        """Reject impossible states before a workflow node can use them."""
        if self.pending_action is not None:
            if self.intent != AgentIntent.TICKET_CREATE:
                raise ValueError(
                    "Only the ticket_create intent may hold a pending action."
                )
            if self.confirmation_status == ConfirmationStatus.NOT_REQUIRED:
                raise ValueError(
                    "A pending ticket action must wait for confirmation."
                )
        elif self.confirmation_status != ConfirmationStatus.NOT_REQUIRED:
            raise ValueError(
                "Confirmation status requires a pending ticket action."
            )

        if self.created_ticket_id is not None and not self.can_create_ticket:
            raise ValueError(
                "A ticket ID can only be recorded after confirmed creation."
            )

        return self
