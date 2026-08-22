import json
from pathlib import Path

import pytest

from knowledgeops.agents.function_calling import AgentFunctionCall, AgentModelResponse
from knowledgeops.evaluation import (
    AgentGoldCase,
    ArchiveIsolationMetrics,
    EvaluationCase,
    MultiHopGoldCase,
    RetrievalMetrics,
    evaluate_answer_verifier,
    evaluate_function_calling_agent,
    evaluate_multi_hop_answers,
    evaluate_retriever,
    evaluate_retriever_load,
    load_evaluation_dataset,
    render_evaluation_report,
    write_evaluation_report,
)


class Candidate:
    def __init__(
        self,
        chunk_id: str,
        source_name: str = "",
        lifecycle: str = "active",
    ) -> None:
        self.chunk_id = chunk_id
        self.source_name = source_name
        self.lifecycle = lifecycle


class FakeRetriever:
    async def retrieve(self, query, *, knowledge_base_id, limit, include_archived=False):
        return [Candidate("wrong"), Candidate("relevant-a")][:limit]


class DuplicateEvidenceRetriever:
    async def retrieve(self, query, *, knowledge_base_id, limit, include_archived=False):
        return [Candidate("relevant-a"), Candidate("relevant-a")][:limit]


class FakeFunctionCallingAgent:
    def __init__(self, responses: list[AgentModelResponse]) -> None:
        self.responses = responses

    async def complete(self, messages, *, tool_choice="auto") -> AgentModelResponse:
        return self.responses.pop(0)


class AnswerCandidate:
    def __init__(self, source_name: str, text: str) -> None:
        self.chunk_id = f"chunk-{source_name}"
        self.document_id = f"document-{source_name}"
        self.source_name = source_name
        self.source_type = "markdown"
        self.chunk_index = 0
        self.start_char = 0
        self.end_char = len(text)
        self.text = text
        self.score = 1.0
        self.sources = ("vector", "keyword")
        self.rerank_score = 1.0


class FakeAnswerRetriever:
    async def retrieve(self, query, *, knowledge_base_id, limit):
        return [
            AnswerCandidate("policy.md", "FACT_POLICY"),
            AnswerCandidate("exception.md", "FACT_EXCEPTION"),
        ][:limit]


class FakeAnswerGenerator:
    async def answer_from_citations(self, question, citations):
        if "unknown" in question:
            return "知识库中没有足够信息。"
        return "FACT_POLICY; FACT_EXCEPTION"


class FakeVerifier:
    async def verify(self, *, question, required_facts, should_abstain, answer):
        return "FACT_POLICY" in answer or "没有足够信息" in answer


@pytest.mark.asyncio
async def test_retrieval_evaluation_reports_ndcg_and_latency_percentiles() -> None:
    metrics = await evaluate_retriever(
        FakeRetriever(),
        [EvaluationCase("vpn", "knowledge-base", frozenset({"relevant-a"}))],
        k=2,
    )

    assert metrics.recall_at_k == 1
    assert metrics.mrr == pytest.approx(0.5)
    assert metrics.ndcg_at_k == pytest.approx(1 / 1.5849625)
    assert metrics.p50_latency_ms >= 0
    assert metrics.p95_latency_ms >= metrics.p50_latency_ms


@pytest.mark.asyncio
async def test_retrieval_evaluation_deduplicates_gold_evidence_for_ndcg() -> None:
    metrics = await evaluate_retriever(
        DuplicateEvidenceRetriever(),
        [EvaluationCase("vpn", "knowledge-base", frozenset({"relevant-a"}))],
        k=2,
    )

    assert metrics.recall_at_k == 1
    assert metrics.mrr == 1
    assert metrics.ndcg_at_k == 1


@pytest.mark.asyncio
async def test_retrieval_load_evaluation_keeps_errors_in_the_measurement() -> None:
    class PartiallyFailingRetriever:
        async def retrieve(self, query, *, knowledge_base_id, limit):
            if query == "fail":
                raise RuntimeError("simulated upstream timeout")
            return []

    metrics = await evaluate_retriever_load(
        PartiallyFailingRetriever(),
        [
            EvaluationCase("ok", "kb", frozenset({"a"})),
            EvaluationCase("fail", "kb", frozenset({"b"})),
        ],
        concurrency=2,
    )

    assert metrics.completed_queries == 1
    assert metrics.error_count == 1
    assert metrics.error_rate == 0.5


@pytest.mark.asyncio
async def test_function_calling_evaluation_checks_tool_choice_and_arguments() -> None:
    cases = (
        AgentGoldCase("greeting", "你好", ()),
        AgentGoldCase("tickets", "查看我的工单", ("list_my_tickets",)),
        AgentGoldCase(
            "draft",
            "创建 VPN 工单",
            ("prepare_ticket_draft",),
            requires_confirmation=True,
        ),
    )
    agent = FakeFunctionCallingAgent(
        [
            AgentModelResponse(content="你好", tool_calls=[]),
            AgentModelResponse(
                content=None,
                tool_calls=[
                    AgentFunctionCall("call-tickets", "list_my_tickets", "{}")
                ],
            ),
            AgentModelResponse(
                content=None,
                tool_calls=[
                    AgentFunctionCall(
                        "call-draft",
                        "prepare_ticket_draft",
                        json.dumps(
                            {
                                "title": "VPN 无法连接",
                                "description": "错误代码 619，影响远程办公。",
                                "priority": "high",
                                "category": "network",
                                "impact": "single_user",
                            }
                        ),
                    )
                ],
            ),
        ]
    )

    metrics = await evaluate_function_calling_agent(agent, cases)

    assert metrics.exact_tool_selection_accuracy == 1
    assert metrics.valid_tool_argument_rate == 1
    assert metrics.confirmation_guard_rate == 1


@pytest.mark.asyncio
async def test_agent_evaluation_tracks_clarification_behavior_and_history() -> None:
    cases = (
        AgentGoldCase(
            "clarify",
            "请创建工单",
            (),
            expected_behavior="clarify",
            required_response_keywords=("补充",),
        ),
        AgentGoldCase(
            "followup",
            "优先级 high，仅影响我本人，请生成草稿。",
            ("prepare_ticket_draft",),
            requires_confirmation=True,
            conversation_history=(("user", "VPN 影响工作"), ("assistant", "请补充影响范围")),
        ),
    )
    agent = FakeFunctionCallingAgent(
        [
            AgentModelResponse(content="请补充优先级和影响范围。", tool_calls=[]),
            AgentModelResponse(
                content=None,
                tool_calls=[
                    AgentFunctionCall(
                        "call-draft",
                        "prepare_ticket_draft",
                        json.dumps(
                            {
                                "title": "VPN",
                                "description": "VPN unavailable",
                                "priority": "high",
                                "category": "network",
                                "impact": "single_user",
                            }
                        ),
                    )
                ],
            ),
        ]
    )

    metrics = await evaluate_function_calling_agent(agent, cases)

    assert metrics.exact_tool_selection_accuracy == 1
    assert metrics.clarification_rate == 1
    assert metrics.confirmation_guard_rate == 1


@pytest.mark.asyncio
async def test_multi_hop_and_verifier_evaluation_use_deterministic_gold_facts() -> None:
    cases = (
        MultiHopGoldCase(
            "answerable",
            "two sources",
            "kb",
            frozenset({"policy.md", "exception.md"}),
            ("FACT_POLICY", "FACT_EXCEPTION"),
        ),
        MultiHopGoldCase(
            "abstain",
            "unknown question",
            "kb",
            frozenset(),
            (),
            should_abstain=True,
        ),
    )
    metrics = await evaluate_multi_hop_answers(
        FakeAnswerRetriever(),
        FakeAnswerGenerator(),
        cases,
        k=2,
    )

    assert metrics.evidence_recall_at_k == 1
    assert metrics.answer_fact_recall == 1
    assert metrics.fully_grounded_answer_rate == 1
    assert metrics.grounded_abstention_rate == 1

    verifier_metrics = await evaluate_answer_verifier(FakeVerifier(), cases, metrics.results)
    assert verifier_metrics.agreement_with_gold == 1


def test_versioned_gold_set_loads_and_report_keeps_unmeasured_values_as_tbd(
    tmp_path,
) -> None:
    dataset_path = (
        Path(__file__).parents[1] / "docs" / "evaluation" / "knowledgeops-gold-v0.1.json"
    )
    dataset = load_evaluation_dataset(dataset_path)

    report = render_evaluation_report(dataset)

    assert dataset.dataset_version == "v0.1"
    assert len(dataset.retrieval_cases) == 6
    assert "| No measured run | TBD" in report
    assert "No scores are invented" in report

    report_path, json_path = write_evaluation_report(
        tmp_path,
        dataset,
        retrieval_metrics={
            "hybrid": RetrievalMetrics(
                evaluated_queries=6,
                recall_at_k=0.8,
                mrr=0.7,
                ndcg_at_k=0.75,
                average_latency_ms=20,
                p50_latency_ms=18,
                p95_latency_ms=30,
            )
        },
        historical_retrieval_metrics={
            "hybrid": RetrievalMetrics(
                evaluated_queries=2,
                recall_at_k=0.9,
                mrr=0.85,
                ndcg_at_k=0.88,
                average_latency_ms=21,
                p50_latency_ms=19,
                p95_latency_ms=31,
            )
        },
        archive_isolation_metrics={
            "hybrid": ArchiveIsolationMetrics(
                evaluated_queries=2,
                archive_leakage_rate=0,
                average_latency_ms=20,
                p50_latency_ms=18,
                p95_latency_ms=30,
            )
        },
    )

    report = report_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "| hybrid | 6 | 0.8000" in report
    assert "## Archive Governance" in report
    assert "| hybrid | 2 | 0.9000 | 0.8500 | 2 | 0.0000 |" in report
    assert payload["retrieval_metrics"]["hybrid"]["ndcg_at_k"] == 0.75
    assert payload["historical_retrieval_metrics"]["hybrid"]["recall_at_k"] == 0.9
    assert payload["archive_isolation_metrics"]["hybrid"]["archive_leakage_rate"] == 0


def test_v02_gold_set_has_over_one_hundred_balanced_retrieval_cases() -> None:
    root = Path(__file__).parents[1]
    dataset = load_evaluation_dataset(
        root / "docs" / "evaluation" / "knowledgeops-gold-v0.2.json"
    )
    fixture_names = {
        path.name for path in (root / "docs" / "evaluation" / "fixtures-v0.2").glob("*.md")
    }
    style_counts: dict[str, int] = {}

    for case in dataset.retrieval_cases:
        _domain, style = case.category.split(":", maxsplit=1)
        style_counts[style] = style_counts.get(style, 0) + 1
        assert case.relevant_ids <= fixture_names

    assert dataset.dataset_version == "v0.2"
    assert len(dataset.retrieval_cases) == 120
    assert len(dataset.agent_cases) == 24
    assert len(dataset.security_cases) == 12
    assert len(fixture_names) == 24
    assert style_counts == {
        "direct": 24,
        "paraphrase": 24,
        "contrast": 24,
        "process": 24,
        "boundary": 24,
    }


def test_v03_gold_set_has_five_hundred_cases_and_chat_evaluation_workload() -> None:
    root = Path(__file__).parents[1]
    dataset = load_evaluation_dataset(
        root / "docs" / "evaluation" / "knowledgeops-gold-v0.3.json"
    )
    fixture_names = {
        path.name for path in (root / "docs" / "evaluation" / "fixtures-v0.3").glob("*.md")
    }
    style_counts: dict[str, int] = {}

    for case in dataset.retrieval_cases:
        _domain, style = case.category.split(":", maxsplit=1)
        style_counts[style] = style_counts.get(style, 0) + 1
        assert case.relevant_ids <= fixture_names

    assert dataset.dataset_version == "v0.3"
    assert len(fixture_names) == 100
    assert len(dataset.retrieval_cases) == 500
    assert len(dataset.agent_cases) == 100
    assert len(dataset.security_cases) == 24
    assert style_counts == {
        "direct": 100,
        "paraphrase": 100,
        "contrast": 100,
        "process": 100,
        "boundary": 100,
    }


def test_v04_gold_set_covers_hard_retrieval_multi_hop_and_agent_states() -> None:
    root = Path(__file__).parents[1]
    dataset = load_evaluation_dataset(
        root / "docs" / "evaluation" / "knowledgeops-gold-v0.4.json"
    )
    fixture_names = {
        path.name for path in (root / "docs" / "evaluation" / "fixtures-v0.4").glob("*.md")
    }

    assert dataset.dataset_version == "v0.4"
    assert len(fixture_names) == 160
    assert len(dataset.retrieval_cases) == 800
    assert len(dataset.agent_cases) == 100
    assert len(dataset.multi_hop_cases) == 160
    assert len(dataset.security_cases) == 32
    assert sum(case.expected_behavior == "clarify" for case in dataset.agent_cases) == 15
    assert sum(bool(case.conversation_history) for case in dataset.agent_cases) == 15
    assert sum(case.should_abstain for case in dataset.multi_hop_cases) == 40
    assert all(case.relevant_ids <= fixture_names for case in dataset.retrieval_cases)
    assert all(
        case.required_source_names <= fixture_names
        for case in dataset.multi_hop_cases
        if not case.should_abstain
    )


def test_v041_gold_set_separates_current_history_and_archive_safety() -> None:
    root = Path(__file__).parents[1]
    dataset = load_evaluation_dataset(
        root / "docs" / "evaluation" / "knowledgeops-gold-v0.4.1.json"
    )
    fixture_names = {
        path.name for path in (root / "docs" / "evaluation" / "fixtures-v0.4").glob("*.md")
    }

    assert dataset.dataset_version == "v0.4.1"
    assert len(dataset.retrieval_cases) == 600
    assert len(dataset.historical_retrieval_cases) == 200
    assert all(not name.endswith("-archive.md") for case in dataset.retrieval_cases for name in case.relevant_ids)
    assert all(name.endswith("-archive.md") for case in dataset.historical_retrieval_cases for name in case.relevant_ids)
    assert all(case.relevant_ids <= fixture_names for case in dataset.retrieval_cases)
    assert all(case.relevant_ids <= fixture_names for case in dataset.historical_retrieval_cases)
