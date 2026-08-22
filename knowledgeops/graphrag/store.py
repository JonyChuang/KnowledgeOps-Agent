"""Graph storage contract and its deterministic in-memory implementation."""

from collections.abc import Sequence
from typing import Protocol

from .models import GraphChunk, GraphEntity, normalize_entity_key


class GraphStore(Protocol):
    """Storage boundary for graph writes and graph-based chunk lookup."""

    async def ensure_schema(self) -> None:
        """Create required graph indexes and constraints."""

    async def replace_chunk_entities(
        self,
        chunk: GraphChunk,
        entities: Sequence[GraphEntity],
    ) -> None:
        """Replace all entity mentions belonging to one chunk."""

    async def find_chunks(
        self,
        *,
        knowledge_base_id: str,
        entity_keys: Sequence[str],
        limit: int,
        include_archived: bool = False,
    ) -> list[GraphChunk]:
        """Return chunks linked to the requested entities in one knowledge base."""

    async def close(self) -> None:
        """Release storage resources."""

    async def update_document_lifecycle(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
        lifecycle: str,
    ) -> None:
        """Update source availability without rebuilding graph entities."""

class InMemoryGraphStore:
    """Small deterministic graph store used by unit tests."""

    def __init__(self) -> None:
        self._chunks: dict[str, GraphChunk] = {}
        self._entity_keys_by_chunk: dict[str, set[str]] = {}

    async def ensure_schema(self) -> None:
        return None

    async def replace_chunk_entities(
        self,
        chunk: GraphChunk,
        entities: Sequence[GraphEntity],
    ) -> None:
        self._chunks[chunk.chunk_id] = chunk
        self._entity_keys_by_chunk[chunk.chunk_id] = {
            entity.key for entity in entities
        }

    async def find_chunks(
        self,
        *,
        knowledge_base_id: str,
        entity_keys: Sequence[str],
        limit: int,
        include_archived: bool = False,
    ) -> list[GraphChunk]:
        if not knowledge_base_id.strip():
            raise ValueError("Knowledge base ID cannot be empty.")
        if limit <= 0:
            raise ValueError("Search limit must be greater than zero.")

        requested_keys = {
            normalize_entity_key(entity_key)
            for entity_key in entity_keys
            if entity_key.strip()
        }
        if not requested_keys:
            return []

        matched_chunks = [
            chunk
            for chunk_id, chunk in self._chunks.items()
            if chunk.knowledge_base_id == knowledge_base_id
            and self._entity_keys_by_chunk[chunk_id] & requested_keys
            and chunk.lifecycle != "draft"
            and (include_archived or chunk.lifecycle != "archived")
        ]
        matched_chunks.sort(
            key=lambda chunk: (
                chunk.document_id,
                chunk.chunk_index,
                chunk.chunk_id,
            )
        )
        return matched_chunks[:limit]

    async def close(self) -> None:
        return None

    async def update_document_lifecycle(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
        lifecycle: str,
    ) -> None:
        self._chunks = {
            chunk_id: (
                GraphChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    source_name=chunk.source_name,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    lifecycle=lifecycle,
                )
                if chunk.knowledge_base_id == knowledge_base_id
                and chunk.document_id == document_id
                else chunk
            )
            for chunk_id, chunk in self._chunks.items()
        }
