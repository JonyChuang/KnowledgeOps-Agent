"""Replaceable reranking contracts and a deterministic baseline."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .hybrid_retriever import HybridRetrievedChunk


class Reranker(Protocol):
    """Reorder citable hybrid candidates for one query."""

    async def rerank(
        self,
        query: str,
        candidates: Sequence[HybridRetrievedChunk],
        *,
        limit: int,
    ) -> list[HybridRetrievedChunk]:
        """Return no more than limit candidates in final display order."""
        ...


class TokenOverlapReranker:
    """Deterministic baseline reranker, replaceable by a model later."""

    async def rerank(
        self,
        query: str,
        candidates: Sequence[HybridRetrievedChunk],
        *,
        limit: int,
    ) -> list[HybridRetrievedChunk]:
        if limit < 1:
            raise ValueError("Rerank limit must be greater than zero.")

        query_terms = _terms(query)
        scored = [
            (
                len(query_terms.intersection(_terms(candidate.text)))
                / len(query_terms)
                if query_terms
                else 0.0,
                candidate,
            )
            for candidate in candidates
        ]
        scored.sort(key=lambda item: (-item[0], -item[1].score, item[1].chunk_id))

        return [
            replace(candidate, rerank_score=score)
            for score, candidate in scored[:limit]
        ]


def _terms(text: str) -> set[str]:
    """Normalize text into case-insensitive terms."""
    return {term.lower() for term in re.findall(r"\w+", text) if term}