"""Grounded multi-hop answer evaluation built on the production RAG contracts."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from typing import Protocol

from ..agents.chat import ChatAnswerGenerator
from ..agents.state import AgentCitation
from .datasets import MultiHopGoldCase


class CitationRetriever(Protocol):
    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
    ) -> Sequence[object]:
        ...


@dataclass(frozen=True)
class MultiHopCaseResult:
    case_id: str
    required_source_names: tuple[str, ...]
    retrieved_source_names: tuple[str, ...]
    evidence_recall: float | None
    evidence_precision: float | None
    answer: str
    fact_recall: float | None
    abstention_passed: bool | None
    answer_passed: bool
    latency_ms: float


@dataclass(frozen=True)
class MultiHopAnswerMetrics:
    evaluated_cases: int
    answerable_cases: int
    abstention_cases: int
    evidence_recall_at_k: float | None
    evidence_precision_at_k: float | None
    answer_fact_recall: float | None
    fully_grounded_answer_rate: float | None
    grounded_abstention_rate: float | None
    average_latency_ms: float
    p95_latency_ms: float
    results: tuple[MultiHopCaseResult, ...]


async def evaluate_multi_hop_answers(
    retriever: CitationRetriever,
    answer_generator: ChatAnswerGenerator,
    cases: Sequence[MultiHopGoldCase],
    *,
    k: int = 4,
) -> MultiHopAnswerMetrics:
    """Measure evidence coverage and fact-grounded answers on multi-document cases.

    The gold facts are deliberately concise, reviewable strings. This evaluator
    does not use another model to score the answer, which keeps its primary
    correctness signal reproducible. A separate optional verifier can audit the
    resulting judgments.
    """
    if not cases:
        raise ValueError("Multi-hop evaluation cases cannot be empty.")
    if k < 1:
        raise ValueError("Multi-hop evaluation k must be greater than zero.")

    results: list[MultiHopCaseResult] = []
    answerable_evidence_recall = 0.0
    answerable_evidence_precision = 0.0
    answerable_fact_recall = 0.0
    fully_grounded = 0
    abstention_passes = 0
    answerable_count = 0
    abstention_count = 0
    latencies: list[float] = []

    for case in cases:
        started = time.perf_counter()
        retrieved = await retriever.retrieve(
            case.question,
            knowledge_base_id=case.knowledge_base_id,
            limit=k,
        )
        citations = [_citation_from_result(item) for item in retrieved[:k]]
        answer = await answer_generator.answer_from_citations(case.question, citations)
        latency_ms = (time.perf_counter() - started) * 1000
        latencies.append(latency_ms)

        source_names = tuple(dict.fromkeys(citation.source_name for citation in citations))
        if case.should_abstain:
            abstention_passed = _is_grounded_abstention(answer)
            abstention_count += 1
            abstention_passes += int(abstention_passed)
            result = MultiHopCaseResult(
                case_id=case.case_id,
                required_source_names=(),
                retrieved_source_names=source_names,
                evidence_recall=None,
                evidence_precision=None,
                answer=answer,
                fact_recall=None,
                abstention_passed=abstention_passed,
                answer_passed=abstention_passed,
                latency_ms=latency_ms,
            )
        else:
            required = case.required_source_names
            retrieved_set = set(source_names)
            evidence_hits = retrieved_set.intersection(required)
            evidence_recall = len(evidence_hits) / len(required)
            evidence_precision = len(evidence_hits) / len(retrieved_set) if retrieved_set else 0.0
            fact_recall = _fact_recall(answer, case.required_facts)
            answer_passed = evidence_recall == 1 and fact_recall == 1
            answerable_count += 1
            answerable_evidence_recall += evidence_recall
            answerable_evidence_precision += evidence_precision
            answerable_fact_recall += fact_recall
            fully_grounded += int(answer_passed)
            result = MultiHopCaseResult(
                case_id=case.case_id,
                required_source_names=tuple(sorted(required)),
                retrieved_source_names=source_names,
                evidence_recall=evidence_recall,
                evidence_precision=evidence_precision,
                answer=answer,
                fact_recall=fact_recall,
                abstention_passed=None,
                answer_passed=answer_passed,
                latency_ms=latency_ms,
            )
        results.append(result)

    return MultiHopAnswerMetrics(
        evaluated_cases=len(cases),
        answerable_cases=answerable_count,
        abstention_cases=abstention_count,
        evidence_recall_at_k=(
            answerable_evidence_recall / answerable_count if answerable_count else None
        ),
        evidence_precision_at_k=(
            answerable_evidence_precision / answerable_count if answerable_count else None
        ),
        answer_fact_recall=(
            answerable_fact_recall / answerable_count if answerable_count else None
        ),
        fully_grounded_answer_rate=(
            fully_grounded / answerable_count if answerable_count else None
        ),
        grounded_abstention_rate=(
            abstention_passes / abstention_count if abstention_count else None
        ),
        average_latency_ms=sum(latencies) / len(latencies),
        p95_latency_ms=_nearest_rank_percentile(latencies, 95),
        results=tuple(results),
    )


def _citation_from_result(result: object) -> AgentCitation:
    """Adapt a production hybrid result without widening the retriever API."""
    return AgentCitation(
        chunk_id=str(result.chunk_id),
        document_id=str(result.document_id),
        source_name=str(result.source_name),
        source_type=str(result.source_type),
        chunk_index=int(result.chunk_index),
        start_char=int(result.start_char),
        end_char=int(result.end_char),
        text=str(result.text),
        score=float(result.score),
        sources=list(getattr(result, "sources", [])),
        rerank_score=getattr(result, "rerank_score", None),
    )


def _fact_recall(answer: str, facts: tuple[str, ...]) -> float:
    normalized_answer = _normalize(answer)
    hits = sum(_normalize(fact) in normalized_answer for fact in facts)
    return hits / len(facts)


def _is_grounded_abstention(answer: str) -> bool:
    normalized_answer = _normalize(answer)
    return any(
        marker in normalized_answer
        for marker in ("没有足够信息", "无法判断", "未找到相关信息", "不能确定")
    )


def _normalize(value: str) -> str:
    return "".join(value.casefold().split())


def _nearest_rank_percentile(values: Sequence[float], percentile: int) -> float:
    ranked = sorted(values)
    return ranked[ceil(percentile / 100 * len(ranked)) - 1]
