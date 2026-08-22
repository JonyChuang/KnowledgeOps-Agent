"""Bounded concurrent retrieval load measurements for offline evaluation."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass

from .retrieval import EvaluationCase, Retriever, _nearest_rank_percentile


@dataclass(frozen=True)
class RetrievalLoadMetrics:
    concurrency: int
    attempted_queries: int
    completed_queries: int
    error_count: int
    error_rate: float
    throughput_queries_per_second: float
    average_latency_ms: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None


async def evaluate_retriever_load(
    retriever: Retriever,
    cases: Sequence[EvaluationCase],
    *,
    concurrency: int,
    limit: int = 5,
) -> RetrievalLoadMetrics:
    """Run a fixed query set concurrently and preserve failed requests as data."""
    if not cases:
        raise ValueError("Load evaluation cases cannot be empty.")
    if concurrency < 1:
        raise ValueError("Load evaluation concurrency must be greater than zero.")
    if limit < 1:
        raise ValueError("Load evaluation limit must be greater than zero.")

    semaphore = asyncio.Semaphore(concurrency)

    async def run_case(case: EvaluationCase) -> float | None:
        async with semaphore:
            started = time.perf_counter()
            try:
                await retriever.retrieve(
                    case.query,
                    knowledge_base_id=case.knowledge_base_id,
                    limit=limit,
                )
            except Exception:  # noqa: BLE001 - error rate is a load-test output
                return None
            return (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    latencies = [latency for latency in await asyncio.gather(*(run_case(case) for case in cases)) if latency is not None]
    elapsed_seconds = time.perf_counter() - started
    completed = len(latencies)
    errors = len(cases) - completed
    return RetrievalLoadMetrics(
        concurrency=concurrency,
        attempted_queries=len(cases),
        completed_queries=completed,
        error_count=errors,
        error_rate=errors / len(cases),
        throughput_queries_per_second=completed / elapsed_seconds if elapsed_seconds else 0.0,
        average_latency_ms=sum(latencies) / completed if completed else None,
        p50_latency_ms=_nearest_rank_percentile(latencies, 50) if latencies else None,
        p95_latency_ms=_nearest_rank_percentile(latencies, 95) if latencies else None,
    )
