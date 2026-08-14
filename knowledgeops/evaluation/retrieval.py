"""Offline retrieval evaluation metrics."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class RetrievedItem(Protocol):
    chunk_id: str


class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
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
    average_latency_ms: float


async def evaluate_retriever(
    retriever: Retriever,
    cases: Sequence[EvaluationCase],
    *,
    k: int = 5,
) -> RetrievalMetrics:
    """Evaluate macro Recall@k, MRR, and average retrieval latency."""
    if not cases:
        raise ValueError("Evaluation cases cannot be empty.")
    if k < 1:
        raise ValueError("Evaluation k must be greater than zero.")

    recall_total = 0.0
    mrr_total = 0.0
    latency_total = 0.0

    for case in cases:
        started = time.perf_counter()
        results = await retriever.retrieve(
            case.query,
            knowledge_base_id=case.knowledge_base_id,
            limit=k,
        )
        latency_total += (time.perf_counter() - started) * 1000

        ranked_ids = [result.chunk_id for result in results[:k]]
        hits = set(ranked_ids).intersection(case.relevant_chunk_ids)
        recall_total += len(hits) / len(case.relevant_chunk_ids)

        for rank, chunk_id in enumerate(ranked_ids, start=1):
            if chunk_id in case.relevant_chunk_ids:
                mrr_total += 1 / rank
                break

    count = len(cases)
    return RetrievalMetrics(
        evaluated_queries=count,
        recall_at_k=recall_total / count,
        mrr=mrr_total / count,
        average_latency_ms=latency_total / count,
    )