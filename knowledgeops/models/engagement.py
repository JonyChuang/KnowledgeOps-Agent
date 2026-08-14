"""Employee-owned favorites, recent visits, and Agent-answer feedback."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_id, utc_now


class WorkspaceItemType(str, Enum):
    """Stable object categories that can be favorited or revisited."""

    KNOWLEDGE_BASE = "knowledge_base"
    DOCUMENT = "document"
    GRAPH = "graph"
    TICKET = "ticket"
    CONVERSATION = "conversation"


class AgentFeedbackType(str, Enum):
    """Structured signals employees can send about an Agent answer."""

    HELPFUL = "helpful"
    UNHELPFUL = "unhelpful"
    STALE_CITATION = "stale_citation"
    INCORRECT_ANSWER = "incorrect_answer"


class AgentFeedbackStatus(str, Enum):
    """Lifecycle retained for a later knowledge-maintenance management view."""

    OPEN = "open"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"


class Favorite(TimestampMixin, Base):
    """One employee's reusable shortcut to a workspace object."""

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("actor", "entity_type", "entity_id", name="uq_favorite_actor_entity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[WorkspaceItemType] = mapped_column(
        SqlEnum(
            WorkspaceItemType,
            name="workspace_item_type",
            native_enum=False,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str] = mapped_column(Text, default="", nullable=False)
    target_view: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RecentVisit(TimestampMixin, Base):
    """The latest visit time for one employee-object pair."""

    __tablename__ = "recent_visits"
    __table_args__ = (
        UniqueConstraint("actor", "entity_type", "entity_id", name="uq_recent_visit_actor_entity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[WorkspaceItemType] = mapped_column(
        SqlEnum(
            WorkspaceItemType,
            name="workspace_item_type",
            native_enum=False,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str] = mapped_column(Text, default="", nullable=False)
    target_view: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    visited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )


class AgentFeedback(TimestampMixin, Base):
    """One employee's current quality signal for one persisted Agent message."""

    __tablename__ = "agent_feedback"
    __table_args__ = (
        UniqueConstraint("actor", "agent_message_id", name="uq_agent_feedback_actor_message"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    agent_message_id: Mapped[str] = mapped_column(
        ForeignKey("agent_messages.id"),
        nullable=False,
        index=True,
    )
    feedback_type: Mapped[AgentFeedbackType] = mapped_column(
        SqlEnum(
            AgentFeedbackType,
            name="agent_feedback_type",
            native_enum=False,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        index=True,
    )
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[AgentFeedbackStatus] = mapped_column(
        SqlEnum(
            AgentFeedbackStatus,
            name="agent_feedback_status",
            native_enum=False,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        default=AgentFeedbackStatus.OPEN,
        nullable=False,
        index=True,
    )
