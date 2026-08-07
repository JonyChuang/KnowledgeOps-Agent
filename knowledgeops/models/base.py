"""Shared ORM base classes and common persistent fields."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for database records."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """Use UUID strings so SQLite and PostgreSQL share the same primary-key type."""
    return str(uuid4())


class Base(DeclarativeBase):
    """Base class whose metadata is used by Alembic migrations."""


class TimestampMixin:
    """Add creation and update times to business entities."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )