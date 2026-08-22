"""In-memory keyword store used for hybrid retrieval tests."""

import re
from collections.abc import Iterable

from .keyword_store import KeywordPoint, KeywordSearchResult


class FakeKeywordStore:
    """A deterministic keyword store for tests and local demonstrations."""

    def __init__(self, results: Iterable[KeywordSearchResult] = ()) -> None:
        self.results = list(results)

    async def upsert_points(self, points: list[KeywordPoint]) -> None:
        """Insert or replace searchable chunks in memory."""
        existing = {
            result.chunk_id: result
            for result in self.results
        }

        for point in points:
            existing[point.chunk_id] = KeywordSearchResult(
                chunk_id=point.chunk_id,
                score=0.0,
                payload=dict(point.payload),
            )

        self.results = list(existing.values())

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
        include_archived: bool = False,
    ) -> list[KeywordSearchResult]:
        """Return candidates matching query terms in one knowledge base."""
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Query cannot be empty.")

        if not knowledge_base_id.strip():
            raise ValueError("Knowledge base ID cannot be empty.")

        if limit < 1:
            raise ValueError("Search limit must be greater than zero.")

        query_terms = _tokenize(clean_query)
        matched: list[KeywordSearchResult] = []

        for result in self.results:
            result_kb_id = result.payload.get("knowledge_base_id")
            if str(result_kb_id) != knowledge_base_id:
                continue
            lifecycle = str(result.payload.get("document_lifecycle", "active")).lower()
            if lifecycle == "draft" or (lifecycle == "archived" and not include_archived):
                continue

            text = str(result.payload.get("text", ""))
            text_terms = _tokenize(text)
            matched_terms = query_terms.intersection(text_terms)

            if not matched_terms:
                continue

            matched.append(
                KeywordSearchResult(
                    chunk_id=result.chunk_id,
                    score=float(len(matched_terms)),
                    payload=dict(result.payload),
                )
            )

        matched.sort(key=lambda result: (-result.score, result.chunk_id))
        return matched[:limit]

    async def close(self) -> None:
        """Match the production store lifecycle without holding resources."""

    async def update_document_lifecycle(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
        lifecycle: str,
    ) -> None:
        self.results = [
            KeywordSearchResult(
                chunk_id=result.chunk_id,
                score=result.score,
                payload=(
                    {**result.payload, "document_lifecycle": lifecycle}
                    if result.payload.get("knowledge_base_id") == knowledge_base_id
                    and result.payload.get("document_id") == document_id
                    else result.payload
                ),
            )
            for result in self.results
        ]


def _tokenize(text: str) -> set[str]:
    """Normalize text into case-insensitive alphanumeric terms."""
    return {
        token.lower()
        for token in re.findall(r"\w+", text)
        if token
    }
