"""Reciprocal Rank Fusion for hybrid retrieval candidates."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .hybrid import HybridCandidate


@dataclass(frozen=True)
class FusedCandidate:
    """One candidate after combining ranked retrieval results."""

    chunk_id: str
    score: float
    payload: dict[str, Any]
    sources: tuple[str, ...]


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[HybridCandidate]],
    *,
    k: int = 60,
    limit: int | None = None,
) -> list[FusedCandidate]:
    """Combine ranked candidate lists using reciprocal rank fusion."""
    if k < 1:
        raise ValueError("RRF constant k must be greater than zero.")

    if limit is not None and limit < 1:
        raise ValueError("RRF limit must be greater than zero.")

    fused: dict[str, FusedCandidate] = {}

    for ranked_list in ranked_lists:
        seen_in_list: set[str] = set()
        unique_rank = 0

        for candidate in ranked_list:
            if candidate.chunk_id in seen_in_list:
                continue

            seen_in_list.add(candidate.chunk_id)
            # Duplicate results should neither gain score nor penalize later candidates.
            unique_rank += 1
            contribution = 1.0 / (k + unique_rank)
            existing = fused.get(candidate.chunk_id)

            if existing is None:
                fused[candidate.chunk_id] = FusedCandidate(
                    chunk_id=candidate.chunk_id,
                    score=contribution,
                    payload=dict(candidate.payload),
                    sources=(candidate.source,),
                )
                continue

            sources = existing.sources
            if candidate.source not in sources:
                sources = (*sources, candidate.source)

            fused[candidate.chunk_id] = FusedCandidate(
                chunk_id=existing.chunk_id,
                score=existing.score + contribution,
                payload=existing.payload,
                sources=sources,
            )

    ordered = sorted(
        fused.values(),
        key=lambda candidate: (-candidate.score, candidate.chunk_id),
    )

    if limit is None:
        return ordered

    return ordered[:limit]