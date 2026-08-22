"""Tests for hybrid retrieval orchestration."""

from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from knowledgeops.rag import (
    DeterministicEmbeddingProvider,
    FakeKeywordStore,
    HybridRetriever,
    KeywordPoint,
    KeywordSearchResult,
    QdrantVectorStore,
    SemanticRetriever,
    TokenOverlapReranker,
    VectorPoint,
    VectorSearchResult,
)
from knowledgeops.rag.query_planning import build_multi_source_query_plan


def payload(
    *,
    knowledge_base_id: str,
    document_id: str,
    source_name: str,
    text: str,
) -> dict[str, object]:
    """Build the citation payload shared by both retrieval stores."""
    return {
        "knowledge_base_id": knowledge_base_id,
        "document_id": document_id,
        "source_name": source_name,
        "source_type": "markdown",
        "chunk_index": 0,
        "start_char": 0,
        "end_char": len(text),
        "text": text,
    }


@pytest.mark.asyncio
async def test_hybrid_retriever_fuses_two_recallers_and_keeps_citations():
    """One support chunk from both stores should get two RRF contributions."""
    client = AsyncQdrantClient(location=":memory:")
    vector_store = QdrantVectorStore(
        client,
        collection_name="hybrid_retriever_test_chunks",
        dimensions=8,
    )
    embedding_provider = DeterministicEmbeddingProvider(dimensions=8)
    keyword_store = FakeKeywordStore()
    semantic_retriever = SemanticRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )
    
    retriever = HybridRetriever(
        semantic_retriever=semantic_retriever,
        keyword_store=keyword_store,
        reranker=TokenOverlapReranker(),
    )

    support_chunk_id = str(uuid4())
    finance_chunk_id = str(uuid4())
    support_text = "Restart the API service after changing environment variables."
    finance_text = "Submit expense reimbursement receipts before Friday."

    support_payload = payload(
        knowledge_base_id="support",
        document_id="support-document",
        source_name="support-runbook.md",
        text=support_text,
    )
    finance_payload = payload(
        knowledge_base_id="finance",
        document_id="finance-document",
        source_name="finance-policy.md",
        text=finance_text,
    )
    vectors = await embedding_provider.embed_texts([support_text, finance_text])

    try:
        await vector_store.upsert_points(
            [
                VectorPoint(
                    vector_id=support_chunk_id,
                    vector=vectors[0],
                    payload=support_payload,
                ),
                VectorPoint(
                    vector_id=finance_chunk_id,
                    vector=vectors[1],
                    payload=finance_payload,
                ),
            ]
        )
        await keyword_store.upsert_points(
            [
                KeywordPoint(
                    chunk_id=support_chunk_id,
                    payload=support_payload,
                ),
                KeywordPoint(
                    chunk_id=finance_chunk_id,
                    payload=finance_payload,
                ),
            ]
        )

        results = await retriever.retrieve(
            "restart API service environment variables",
            knowledge_base_id="support",
        )

        assert len(results) == 1
        assert results[0].chunk_id == support_chunk_id
        assert results[0].score == pytest.approx(2 / 61)
        assert results[0].sources == ("vector", "keyword")
        assert results[0].knowledge_base_id == "support"
        assert results[0].document_id == "support-document"
        assert results[0].source_name == "support-runbook.md"
        assert results[0].text == support_text
        assert results[0].rerank_score == pytest.approx(1.0)
    finally:
        await vector_store.close()


class NeverCalledSemanticRetriever:
    """Fail if invalid input reaches the vector retriever."""

    async def retrieve_vector_results(self, *args, **kwargs):
        raise AssertionError("Vector retrieval should not be called.")


class NeverCalledKeywordStore:
    """Fail if invalid input reaches keyword retrieval."""

    async def search(self, *args, **kwargs):
        raise AssertionError("Keyword retrieval should not be called.")


class QueryAwareSemanticRetriever:
    """Return a role-specific candidate list and record each focused recall."""

    def __init__(self, results_by_role: dict[str, list[VectorSearchResult]]) -> None:
        self.results_by_role = results_by_role
        self.calls: list[str] = []

    async def retrieve_vector_results(self, query: str, **kwargs) -> list[VectorSearchResult]:
        self.calls.append(query)
        return list(self.results_by_role[_query_role(query)])


class QueryAwareKeywordStore:
    def __init__(self, results_by_role: dict[str, list[KeywordSearchResult]]) -> None:
        self.results_by_role = results_by_role
        self.calls: list[str] = []

    async def search(self, query: str, **kwargs) -> list[KeywordSearchResult]:
        self.calls.append(query)
        return list(self.results_by_role[_query_role(query)])

    async def close(self) -> None:
        return None


def _query_role(query: str) -> str:
    normalized = query.casefold().strip()
    if normalized.endswith(" policy"):
        return "policy"
    if normalized.endswith(" procedure"):
        return "procedure"
    return "primary"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "knowledge_base_id", "limit", "message"),
    [
        ("   ", "support", 5, "Query cannot be empty"),
        ("restart service", "   ", 5, "Knowledge base ID cannot be empty"),
        ("restart service", "support", 0, "Search limit must be greater than zero"),
    ],
)
async def test_hybrid_retriever_validates_request_before_recalling(
    query: str,
    knowledge_base_id: str,
    limit: int,
    message: str,
):
    """Invalid requests must fail before either external retriever is called."""
    retriever = HybridRetriever(
        semantic_retriever=NeverCalledSemanticRetriever(),
        keyword_store=NeverCalledKeywordStore(),
    )

    with pytest.raises(ValueError, match=message):
        await retriever.retrieve(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
        )


def test_multi_source_query_plan_expands_only_explicit_evidence_roles() -> None:
    plan = build_multi_source_query_plan(
        "For a VPN incident, combine the policy and procedure."
    )

    assert plan.primary_query == "For a VPN incident, combine the policy and procedure."
    assert [facet.name for facet, _query in plan.facet_queries] == [
        "policy",
        "procedure",
    ]
    assert all(query.endswith(facet.query_suffix) for facet, query in plan.facet_queries)
    assert build_multi_source_query_plan("How do I connect to VPN?").is_multi_source is False


@pytest.mark.asyncio
async def test_hybrid_retriever_prioritizes_distinct_sources_for_multi_source_question():
    def vector_result(role: str) -> VectorSearchResult:
        return VectorSearchResult(
            f"{role}-vector",
            1.0,
            payload(
                knowledge_base_id="support",
                document_id=f"{role}-document",
                source_name=f"{role}.md",
                text=f"VPN {role} evidence",
            ),
        )

    def keyword_result(role: str) -> KeywordSearchResult:
        return KeywordSearchResult(
            f"{role}-vector",
            1.0,
            payload(
                knowledge_base_id="support",
                document_id=f"{role}-document",
                source_name=f"{role}.md",
                text=f"VPN {role} evidence",
            ),
        )

    roles = ("primary", "policy", "procedure")
    semantic_retriever = QueryAwareSemanticRetriever(
        {role: [vector_result(role)] for role in roles}
    )
    keyword_store = QueryAwareKeywordStore(
        {role: [keyword_result(role)] for role in roles}
    )
    retriever = HybridRetriever(
        semantic_retriever=semantic_retriever,
        keyword_store=keyword_store,
        candidate_limit=5,
        max_chunks_per_document=1,
    )

    results = await retriever.retrieve(
        "For a VPN incident, combine policy and procedure.",
        knowledge_base_id="support",
        limit=2,
    )

    assert [result.source_name for result in results] == ["policy.md", "procedure.md"]
    assert len(semantic_retriever.calls) == 3
    assert len(keyword_store.calls) == 3
