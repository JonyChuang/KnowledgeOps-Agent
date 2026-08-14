"""Pydantic contracts for the notification center."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models import NotificationType


class NotificationRead(BaseModel):
    """One notification visible only to its intended recipient."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: NotificationType
    title: str
    content: str
    entity_type: str
    entity_id: str
    target_view: str
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime


class NotificationListRead(BaseModel):
    """A paginated notification list together with the global unread count."""

    items: list[NotificationRead] = Field(default_factory=list)
    total: int = Field(ge=0)
    unread_count: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
