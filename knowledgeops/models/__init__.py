"""Public model imports and ORM metadata registration."""

from .audit import AuditEvent
from .base import Base
from .chunk import DocumentChunk
from .conversation import AgentConversation, AgentMessage
from .engagement import (
    AgentFeedback,
    AgentFeedbackStatus,
    AgentFeedbackType,
    Favorite,
    RecentVisit,
    WorkspaceItemType,
)
from .knowledge import Document, DocumentLifecycle, DocumentStatus, KnowledgeBase
from .notification import Notification, NotificationType
from .ticket import (
    Ticket,
    TicketActivity,
    TicketEscalationLevel,
    TicketImpact,
    TicketPriority,
    TicketStatus,
)
from .user import AuthSession, User, UserRole

__all__ = [
    "AgentConversation",
    "AgentFeedback",
    "AgentFeedbackStatus",
    "AgentFeedbackType",
    "AgentMessage",
    "AuditEvent",
    "AuthSession",
    "Base",
    "Document",
    "DocumentChunk",
    "DocumentLifecycle",
    "DocumentStatus",
    "Favorite",
    "KnowledgeBase",
    "Notification",
    "NotificationType",
    "RecentVisit",
    "Ticket",
    "TicketActivity",
    "TicketEscalationLevel",
    "TicketImpact",
    "TicketPriority",
    "TicketStatus",
    "User",
    "UserRole",
    "WorkspaceItemType",
]
