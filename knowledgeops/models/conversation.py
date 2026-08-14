"""Persistent conversation records shown in the Agent workspace."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_id


class AgentConversation(TimestampMixin, Base):
    """One employee-owned thread displayed in the Agent and workbench views."""

    __tablename__ = "agent_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), default="新对话", nullable=False)
    knowledge_base_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    messages: Mapped[list[AgentMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class AgentMessage(TimestampMixin, Base):
    """A durable user message or Agent turn belonging to a conversation."""

    __tablename__ = "agent_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_agent_message_sequence",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        unique=True,
        index=True,
    )
    turn_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    pending_action: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_ticket_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ticket_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped[AgentConversation] = relationship(back_populates="messages")
