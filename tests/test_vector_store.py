"""Tests for the Qdrant vector storage adapter."""

from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from knowledgeops.rag import QdrantVectorStore, VectorPoint


@pytest.mark.asyncio
async def test_qdrant_store_creates_collection_and_reads_payload():
    """Vectors and source metadata should be retrievable after upsert."""
    client = AsyncQdrantClient(location=":memory:")
    store = QdrantVectorStore(
        client,
        collection_name="test_chunks",
        dimensions=3,
    )
    vector_id = str(uuid4())

    try:
        await store.upsert_points(
            [
                VectorPoint(
                    vector_id=vector_id,
                    vector=[0.1, 0.2, 0.3],
                    payload={
                        "document_id": "document-1",
                        "chunk_index": 0,
                        "source_name": "guide.md",
                    },
                )
            ]
        )

        payload = await store.get_payload(vector_id)
        collection = await client.get_collection("test_chunks")

        assert payload is not None
        assert payload["document_id"] == "document-1"
        assert payload["chunk_index"] == 0
        assert collection.config.params.vectors.size == 3

    finally:
        await store.close()


@pytest.mark.asyncio
async def test_qdrant_store_rejects_wrong_vector_dimension():
    """A vector with the wrong length must fail before network writes."""
    client = AsyncQdrantClient(location=":memory:")
    store = QdrantVectorStore(
        client,
        collection_name="test_chunks",
        dimensions=3,
    )

    try:
        with pytest.raises(ValueError):
            await store.upsert_points(
                [
                    VectorPoint(
                        vector_id=str(uuid4()),
                        vector=[0.1, 0.2],
                        payload={},
                    )
                ]
            )

        with pytest.raises(ValueError):
            await store.search(
                query_vector=[0.1, 0.2],
            )
    finally:
        await store.close()

@pytest.mark.asyncio
async def test_qdrant_store_searches_with_knowledge_base_filter():
    """Vector search must return only chunks from the requested knowledge base."""
    client = AsyncQdrantClient(location=":memory:")
    store = QdrantVectorStore(
        client,
        collection_name="search_test_chunks",
        dimensions=3,
    )
    support_vector_id = str(uuid4())
    finance_vector_id = str(uuid4())

    try:
        await store.upsert_points(
            [
                VectorPoint(
                    vector_id=support_vector_id,
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "knowledge_base_id": "support",
                        "document_id": "support-document",
                        "source_name": "support-guide.md",
                        "chunk_index": 0,
                    },
                ),
                VectorPoint(
                    vector_id=finance_vector_id,
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "knowledge_base_id": "finance",
                        "document_id": "finance-document",
                        "source_name": "finance-guide.md",
                        "chunk_index": 0,
                    },
                ),
            ]
        )

        results = await store.search(
            query_vector=[1.0, 0.0, 0.0],
            knowledge_base_id="support",
        )

        assert [result.vector_id for result in results] == [support_vector_id]
        assert results[0].score == pytest.approx(1.0)
        assert results[0].payload["source_name"] == "support-guide.md"
    finally:
        await store.close()