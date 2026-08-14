"""Pydantic contracts for knowledge-base and document HTTP APIs."""

from datetime import datetime
from typing import Literal

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


class WebPageImportCreate(BaseModel):
    """Validated URL and optional display name for webpage ingestion."""

    url: str = Field(min_length=1, max_length=2_048)
    source_name: str | None = Field(default=None, min_length=1, max_length=255)

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


class DocumentIndexTaskRead(BaseModel):
    """Acknowledgement returned after an indexing task is queued."""

    document_id: str
    task_id: str
    status: Literal["queued"] = "queued"


class SearchRequest(BaseModel):
    """Validated semantic-search input for one knowledge base."""

    query: str = Field(min_length=1, max_length=4_000)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResultRead(BaseModel):
    """One citable document chunk returned by semantic search."""

    chunk_id: str
    score: float
    sources: list[str]
    document_id: str
    source_name: str
    source_type: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str
    rerank_score: float | None = None


class GraphSearchResultRead(BaseModel):
    """One document chunk returned through entity-based graph retrieval."""

    chunk_id: str
    document_id: str
    knowledge_base_id: str
    source_name: str
    chunk_index: int
    text: str