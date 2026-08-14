"""Common candidate structures for hybrid retrieval."""

from dataclasses import dataclass
from typing import Any, Literal

from .keyword_store import KeywordSearchResult
from .vector_store import VectorSearchResult


@dataclass(frozen=True)
class HybridCandidate:
    """One candidate returned by either vector or keyword retrieval."""

    chunk_id: str
    score: float
    payload: dict[str, Any]
    source: Literal["vector", "keyword"]


def vector_candidates(
    results: list[VectorSearchResult],
    *,
    knowledge_base_id: str,
) -> list[HybridCandidate]:
    """Convert Qdrant results into common hybrid candidates."""
    return [
        _from_payload(
            chunk_id=result.vector_id,
            score=result.score,
            payload=result.payload,
            source="vector",
            knowledge_base_id=knowledge_base_id,
        )
        for result in results
    ]


def keyword_candidates(
    results: list[KeywordSearchResult],
    *,
    knowledge_base_id: str,
) -> list[HybridCandidate]:
    """Convert BM25 results into common hybrid candidates."""
    return [
        _from_payload(
            chunk_id=result.chunk_id,
            score=result.score,
            payload=result.payload,
            source="keyword",
            knowledge_base_id=knowledge_base_id,
        )
        for result in results
    ]


def _from_payload(
    *,
    chunk_id: str,
    score: float,
    payload: dict[str, Any],
    source: Literal["vector", "keyword"],
    knowledge_base_id: str,
) -> HybridCandidate:
    """Validate the knowledge-base boundary before fusion."""
    if not knowledge_base_id.strip():
        raise ValueError("Knowledge base ID cannot be empty.")

    result_knowledge_base_id = payload.get("knowledge_base_id")
    if result_knowledge_base_id is None:
        raise ValueError("Retrieval result is missing knowledge_base_id.")

    if str(result_knowledge_base_id) != knowledge_base_id:
        raise ValueError("Retrieval result belongs to another knowledge base.")

    if not chunk_id.strip():
        raise ValueError("Retrieval result is missing chunk_id.")

    return HybridCandidate(
        chunk_id=chunk_id,
        score=float(score),
        payload=dict(payload),
        source=source,
    )