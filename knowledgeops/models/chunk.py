"""Persistent text chunks produced from source documents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_id

if TYPE_CHECKING:
    # Imported only for static type checking to avoid a runtime circular import.
    from .knowledge import Document


class DocumentChunk(TimestampMixin, Base):
    """One searchable text fragment belonging to a source document."""

    __tablename__ = "document_chunks"

    __table_args__ = (
        # A document cannot contain two chunks with the same order number.
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunk_index",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )

    # The position of this chunk in the original document.
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # The exact text sent to the embedding model later.
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Character offsets allow the UI to explain the source location.
    start_char: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    end_char: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Qdrant point ID is filled after vector indexing succeeds.
    vector_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Store the model name so future re-indexing can be audited.
    embedding_model: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    document: Mapped[Document] = relationship(
        back_populates="chunks",
    )