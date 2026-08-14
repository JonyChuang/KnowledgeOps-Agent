"""Pydantic contracts for ticket operations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import (
    TicketEscalationLevel,
    TicketImpact,
    TicketPriority,
    TicketStatus,
)


class TicketCreate(BaseModel):
    """Validated input for creating a ticket."""

    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=1, max_length=20_000)
    priority: TicketPriority = TicketPriority.MEDIUM
    category: str = Field(default="general", min_length=2, max_length=80)
    impact: TicketImpact = TicketImpact.SINGLE_USER


class TicketRead(BaseModel):
    """Public ticket fields returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    requester: str
    category: str = "general"
    impact: TicketImpact = TicketImpact.SINGLE_USER
    assignee: str | None = None
    escalation_level: TicketEscalationLevel = TicketEscalationLevel.NONE
    sla_due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("category", mode="before")
    @classmethod
    def default_missing_category(cls, value: object) -> object:
        """Read legacy ticket-like objects safely during the schema rollout."""
        return value or "general"

    @field_validator("impact", mode="before")
    @classmethod
    def default_missing_impact(cls, value: object) -> object:
        """Keep older Agent tool adapters compatible with the new read model."""
        return value or TicketImpact.SINGLE_USER

    @field_validator("escalation_level", mode="before")
    @classmethod
    def default_missing_escalation_level(cls, value: object) -> object:
        """Keep pre-escalation Agent adapters compatible with the read model."""
        return value or TicketEscalationLevel.NONE


class TicketListRead(BaseModel):
    """A scoped ticket page with enough metadata for a list UI."""

    items: list[TicketRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class TicketActivityRead(BaseModel):
    """A single immutable event shown in the ticket detail timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    actor: str
    content: str | None = None
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class TicketDetailRead(TicketRead):
    """One employee-owned ticket with its complete visible activity history."""

    activities: list[TicketActivityRead] = Field(default_factory=list)


class TicketCommentCreate(BaseModel):
    """A requester reply or supplemental detail for an active ticket."""

    content: str = Field(min_length=1, max_length=4_000)


class TicketReopenCreate(BaseModel):
    """The requester must explain why a resolved ticket needs more work."""

    reason: str = Field(min_length=2, max_length=4_000)


class TicketWorkflowReasonCreate(BaseModel):
    """A service-desk action that must leave a useful visible reason."""

    reason: str = Field(min_length=2, max_length=4_000)


class TicketAssignCreate(BaseModel):
    """Assign one active ticket to a named service-desk operator."""

    assignee: str = Field(min_length=2, max_length=120)

    @field_validator("assignee")
    @classmethod
    def normalize_assignee(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Assignee must contain at least two characters.")
        return normalized


class TicketPriorityUpdateCreate(BaseModel):
    """A service-desk priority adjustment with a visible business reason."""

    priority: TicketPriority
    reason: str = Field(min_length=2, max_length=4_000)


class TicketEscalateCreate(BaseModel):
    """Escalate a ticket to a higher support responsibility level."""

    level: TicketEscalationLevel
    reason: str = Field(min_length=2, max_length=4_000)
