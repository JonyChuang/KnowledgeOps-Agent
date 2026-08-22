"""Domain types shared by the GraphRAG layer."""

from dataclasses import dataclass


def normalize_entity_key(name: str) -> str:
    """Create a stable, case-insensitive identity for an entity name."""
    normalized_name = " ".join(name.strip().split())
    if not normalized_name:
        raise ValueError("Entity name cannot be empty.")

    return normalized_name.casefold()


@dataclass(frozen=True, slots=True)
class GraphEntity:
    """One normalized entity mentioned by one or more document chunks."""

    name: str
    key: str

    @classmethod
    def from_name(cls, name: str) -> "GraphEntity":
        normalized_name = " ".join(name.strip().split())
        return cls(
            name=normalized_name,
            key=normalize_entity_key(normalized_name),
        )


@dataclass(frozen=True, slots=True)
class GraphChunk:
    """The searchable document-chunk data stored in the knowledge graph."""

    chunk_id: str
    document_id: str
    knowledge_base_id: str
    source_name: str
    chunk_index: int
    text: str
    lifecycle: str = "active"
