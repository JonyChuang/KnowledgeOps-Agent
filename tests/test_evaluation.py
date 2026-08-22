from dataclasses import dataclass

import pytest

from knowledgeops.evaluation import (
    EvaluationCase,
    evaluate_archive_isolation,
    evaluate_retriever,
)


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    source_name: str = ""
    lifecycle: str = "active"


class FakeRetriever:
    def __init__(self, responses):
        self.responses = responses

    async def retrieve(self, query, *, knowledge_base_id, limit, include_archived=False):
        return self.responses[query][:limit]


@pytest.mark.asyncio
async def test_evaluate_retriever_calculates_recall_mrr_and_latency():
    retriever = FakeRetriever(
        {
            "q1": [
                Candidate("wrong"),
                Candidate("a"),
            ],
            "q2": [
                Candidate("b"),
                Candidate("wrong"),
            ],
        }
    )
    cases = [
        EvaluationCase("q1", "support", frozenset({"a"})),
        EvaluationCase("q2", "support", frozenset({"b", "c"})),
    ]

    metrics = await evaluate_retriever(retriever, cases, k=2)

    assert metrics.evaluated_queries == 2
    assert metrics.recall_at_k == pytest.approx(0.75)
    assert metrics.mrr == pytest.approx(0.75)
    assert metrics.average_latency_ms >= 0


@pytest.mark.asyncio
async def test_evaluate_retriever_rejects_empty_cases():
    with pytest.raises(ValueError, match="cases cannot be empty"):
        await evaluate_retriever(FakeRetriever({}), [], k=5)


@pytest.mark.asyncio
async def test_archive_isolation_reports_archived_result_leakage():
    metrics = await evaluate_archive_isolation(
        FakeRetriever({"history": [Candidate("old", "old.md", "archived")]}),
        [EvaluationCase("history", "support", frozenset({"old"}))],
        k=1,
    )

    assert metrics.evaluated_queries == 1
    assert metrics.archive_leakage_rate == 1
