from typing import Literal

from pydantic import BaseModel, Field


class AgentTurnCreate(BaseModel):
    user_message: str = Field(min_length=1, max_length=4_000)
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )
    knowledge_base_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )


class AgentConfirmationCreate(BaseModel):
    approved: bool


class AgentCitationRead(BaseModel):
    chunk_id: str
    document_id: str
    source_name: str
    source_type: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str
    score: float
    sources: list[str]
    rerank_score: float | None = None


class AgentPendingActionRead(BaseModel):
    action_type: Literal["ticket.create"]
    arguments: dict[str, str]


class AgentTurnRead(BaseModel):
    thread_id: str
    conversation_id: str | None = None
    status: Literal[
        "completed",
        "confirmation_required",
        "cancelled",
        "failed",
    ]
    answer: str | None = None
    citations: list[AgentCitationRead] = Field(default_factory=list)
    pending_action: AgentPendingActionRead | None = None
    created_ticket_id: str | None = None
    ticket_ids: list[str] = Field(default_factory=list)
    error: str | None = None
