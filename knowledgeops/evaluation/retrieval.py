"""Offline retrieval evaluation metrics."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import ceil, log2
from typing import Protocol


class RetrievedItem(Protocol):
    chunk_id: str
    source_name: str
    lifecycle: str


class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        include_archived: bool = False,
    ) -> Sequence[RetrievedItem]:
        ...


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    knowledge_base_id: str
    relevant_chunk_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("Evaluation query cannot be empty.")
        if not self.knowledge_base_id.strip():
            raise ValueError("Evaluation knowledge base ID cannot be empty.")
        if not self.relevant_chunk_ids:
            raise ValueError("Evaluation case needs relevant chunk IDs.")


@dataclass(frozen=True)
class RetrievalMetrics:
    evaluated_queries: int
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float


@dataclass(frozen=True)
class ArchiveIsolationMetrics:
    """Measure whether archived sources leak into ordinary employee retrieval."""

    evaluated_queries: int
    archive_leakage_rate: float
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float


async def evaluate_retriever(
    retriever: Retriever,
    cases: Sequence[EvaluationCase],
    *,
    k: int = 5,
    result_identifier: Callable[[RetrievedItem], str] | None = None,
    include_archived: bool = False,
) -> RetrievalMetrics:
    """Evaluate binary relevance recall, ranking quality, and latency.

    ``result_identifier`` keeps the metric implementation independent from how
    a gold set labels evidence. Production runs typically use ``chunk_id``;
    small, curated demos may label evidence by ``source_name`` instead.
    """
    if not cases:
        raise ValueError("Evaluation cases cannot be empty.")
    if k < 1:
        raise ValueError("Evaluation k must be greater than zero.")

    recall_total = 0.0
    mrr_total = 0.0
    ndcg_total = 0.0
    latency_total = 0.0
    latencies_ms: list[float] = []
    identifier = result_identifier or (lambda item: item.chunk_id)

    for case in cases:
        started = time.perf_counter()
        results = await retriever.retrieve(
            case.query,
            knowledge_base_id=case.knowledge_base_id,
            limit=k,
            include_archived=include_archived,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        latency_total += latency_ms
        latencies_ms.append(latency_ms)

        # A source-name gold set evaluates documents, while a retriever returns
        # chunks. Count each document only once so duplicate chunks cannot make
        # a normalized ranking score exceed 1.
        ranked_ids = list(dict.fromkeys(identifier(result) for result in results[:k]))
        hits = set(ranked_ids).intersection(case.relevant_chunk_ids)
        recall_total += len(hits) / len(case.relevant_chunk_ids)

        for rank, chunk_id in enumerate(ranked_ids, start=1):
            if chunk_id in case.relevant_chunk_ids:
                mrr_total += 1 / rank
                break

        dcg = sum(
            1 / log2(rank + 1)
            for rank, chunk_id in enumerate(ranked_ids, start=1)
            if chunk_id in case.relevant_chunk_ids
        )
        ideal_hits = min(k, len(case.relevant_chunk_ids))
        ideal_dcg = sum(1 / log2(rank + 1) for rank in range(1, ideal_hits + 1))
        ndcg_total += dcg / ideal_dcg if ideal_dcg else 0.0

    count = len(cases)
    return RetrievalMetrics(
        evaluated_queries=count,
        recall_at_k=recall_total / count,
        mrr=mrr_total / count,
        ndcg_at_k=ndcg_total / count,
        average_latency_ms=latency_total / count,
        p50_latency_ms=_nearest_rank_percentile(latencies_ms, 50),
        p95_latency_ms=_nearest_rank_percentile(latencies_ms, 95),
    )


async def evaluate_archive_isolation(
    retriever: Retriever,
    cases: Sequence[EvaluationCase],
    *,
    k: int = 5,
) -> ArchiveIsolationMetrics:
    """Verify ordinary retrieval never exposes an archived source.

    The cases intentionally ask about known historical documents, but run with
    ``include_archived=False`` just as an employee search does. A query is a
    leak when any returned result still carries archived lifecycle metadata.
    """
    if not cases:
        raise ValueError("Archive isolation cases cannot be empty.")
    if k < 1:
        raise ValueError("Archive isolation k must be greater than zero.")

    leaked_queries = 0
    latency_total = 0.0
    latencies_ms: list[float] = []
    for case in cases:
        started = time.perf_counter()
        results = await retriever.retrieve(
            case.query,
            knowledge_base_id=case.knowledge_base_id,
            limit=k,
            include_archived=False,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        latency_total += latency_ms
        latencies_ms.append(latency_ms)
        leaked_queries += int(
            any(result.lifecycle.strip().lower() == "archived" for result in results)
        )

    count = len(cases)
    return ArchiveIsolationMetrics(
        evaluated_queries=count,
        archive_leakage_rate=leaked_queries / count,
        average_latency_ms=latency_total / count,
        p50_latency_ms=_nearest_rank_percentile(latencies_ms, 50),
        p95_latency_ms=_nearest_rank_percentile(latencies_ms, 95),
    )


def _nearest_rank_percentile(values: Sequence[float], percentile: int) -> float:
    """Return a stable nearest-rank latency percentile for a small gold set."""
    if not values:
        raise ValueError("values cannot be empty")
    if not 0 < percentile <= 100:
        raise ValueError("percentile must be between 1 and 100")
    ranked = sorted(values)
    return ranked[ceil(percentile / 100 * len(ranked)) - 1]
