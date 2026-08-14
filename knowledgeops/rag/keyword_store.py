"""Contract for keyword/BM25 document-chunk retrieval."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class KeywordPoint:
    """One document chunk and its searchable metadata."""

    chunk_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class KeywordSearchResult:
    """One BM25 match with source metadata."""

    chunk_id: str
    score: float
    payload: dict[str, Any]


class KeywordStore(Protocol):
    """Store and retrieve keyword-ranked chunks from one knowledge base."""

    async def upsert_points(self, points: list[KeywordPoint]) -> None:
        """Insert or replace searchable document chunks."""
        ...

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[KeywordSearchResult]:
        """Return BM25-ranked candidates scoped to one knowledge base."""
        ...

    async def close(self) -> None:
        """Release resources held by the keyword-store client."""
        ...