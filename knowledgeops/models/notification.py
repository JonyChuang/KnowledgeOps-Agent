"""Persistent employee and service-desk notifications."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_id


class NotificationType(str, Enum):
    """A compact category that the notification center can present consistently."""

    TICKET = "ticket"
    SYSTEM = "system"


class Notification(TimestampMixin, Base):
    """One recipient-owned, read-trackable operational notification."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recipient: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(
        SqlEnum(
            NotificationType,
            name="notification_type",
            native_enum=False,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        default=NotificationType.TICKET,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_view: Mapped[str] = mapped_column(String(40), default="tickets", nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
