"""Tests for the semantic retriever."""

from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from knowledgeops.rag import (
    DeterministicEmbeddingProvider,
    QdrantVectorStore,
    SemanticRetriever,
    VectorPoint,
)


@pytest.mark.asyncio
async def test_semantic_retriever_returns_citable_chunks():
    """A matching question should return a chunk from the requested knowledge base."""
    client = AsyncQdrantClient(location=":memory:")
    vector_store = QdrantVectorStore(
        client,
        collection_name="retriever_test_chunks",
        dimensions=8,
    )
    embedding_provider = DeterministicEmbeddingProvider(dimensions=8)
    retriever = SemanticRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    support_text = "Restart the API service after changing environment variables."
    finance_text = "Submit expense reimbursement receipts before Friday."
    vectors = await embedding_provider.embed_texts([support_text, finance_text])

    try:
        await vector_store.upsert_points(
            [
                VectorPoint(
                    vector_id=str(uuid4()),
                    vector=vectors[0],
                    payload={
                        "knowledge_base_id": "support",
                        "document_id": "support-document",
                        "source_name": "support-runbook.md",
                        "source_type": "markdown",
                        "chunk_index": 0,
                        "start_char": 0,
                        "end_char": len(support_text),
                        "text": support_text,
                    },
                ),
                VectorPoint(
                    vector_id=str(uuid4()),
                    vector=vectors[1],
                    payload={
                        "knowledge_base_id": "finance",
                        "document_id": "finance-document",
                        "source_name": "finance-policy.md",
                        "source_type": "markdown",
                        "chunk_index": 0,
                        "start_char": 0,
                        "end_char": len(finance_text),
                        "text": finance_text,
                    },
                ),
            ]
        )

        results = await retriever.retrieve(
            support_text,
            knowledge_base_id="support",
        )

        assert len(results) == 1
        assert results[0].source_name == "support-runbook.md"
        assert results[0].document_id == "support-document"
        assert results[0].text == support_text
        assert results[0].score == pytest.approx(1.0)
    finally:
        await vector_store.close()


@pytest.mark.asyncio
async def test_semantic_retriever_rejects_empty_query():
    """An empty user question must fail before an embedding request is sent."""
    client = AsyncQdrantClient(location=":memory:")
    vector_store = QdrantVectorStore(
        client,
        collection_name="empty_query_test",
        dimensions=8,
    )
    retriever = SemanticRetriever(
        embedding_provider=DeterministicEmbeddingProvider(dimensions=8),
        vector_store=vector_store,
    )

    try:
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await retriever.retrieve(
                "   ",
                knowledge_base_id="support",
            )
    finally:
        await vector_store.close()