"""Pydantic contracts for knowledge-base and document HTTP APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models import DocumentStatus


class KnowledgeBaseCreate(BaseModel):
    """Validated request body for creating a knowledge base."""

    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=4_000)
    department: str = Field(default="general", min_length=1, max_length=80)


class KnowledgeBaseRead(BaseModel):
    """Public knowledge-base fields returned by the API."""

    # SQLAlchemy models can be converted directly into this response object.
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    department: str
    created_at: datetime
    updated_at: datetime


class TextDocumentCreate(BaseModel):
    """Text document accepted before file parsing is added in the RAG stage."""

    source_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=2_000_000)
    source_type: str = Field(default="text", max_length=32)


class DocumentRead(BaseModel):
    """Document metadata and lifecycle state returned to management clients."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base_id: str
    source_name: str
    source_type: str
    status: DocumentStatus
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime