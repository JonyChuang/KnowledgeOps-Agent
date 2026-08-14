"""Ticket persistence models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_id


class TicketPriority(str, Enum):
    """Supported ticket priorities."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketEscalationLevel(str, Enum):
    """Escalation levels that remain independent from ticket priority."""

    NONE = "none"
    TEAM_LEAD = "team_lead"
    MANAGER = "manager"


class TicketStatus(str, Enum):
    """Ticket lifecycle states."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    AWAITING_REQUESTER = "awaiting_requester"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketImpact(str, Enum):
    """How broadly a service interruption affects the organization."""

    SINGLE_USER = "single_user"
    TEAM = "team"
    DEPARTMENT = "department"
    COMPANY = "company"


class Ticket(TimestampMixin, Base):
    """A support ticket created by a user or an Agent tool."""

    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(80),
        default="general",
        nullable=False,
        index=True,
    )
    impact: Mapped[TicketImpact] = mapped_column(
        SqlEnum(
            TicketImpact,
            name="ticket_impact",
            native_enum=False,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        default=TicketImpact.SINGLE_USER,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SqlEnum(
            TicketPriority,
            name="ticket_priority",
            native_enum=False,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        default=TicketPriority.MEDIUM,
        nullable=False,
        index=True,
    )
    status: Mapped[TicketStatus] = mapped_column(
        SqlEnum(
            TicketStatus,
            name="ticket_status",
            native_enum=False,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        default=TicketStatus.OPEN,
        nullable=False,
        index=True,
    )
    requester: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    escalation_level: Mapped[TicketEscalationLevel] = mapped_column(
        SqlEnum(
            TicketEscalationLevel,
            name="ticket_escalation_level",
            native_enum=False,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        default=TicketEscalationLevel.NONE,
        nullable=False,
        index=True,
    )
    sla_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    activities: Mapped[list[TicketActivity]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketActivity.created_at",
    )


class TicketActivity(TimestampMixin, Base):
    """Append-only employee-visible events on one service ticket."""

    __tablename__ = "ticket_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="activities")
