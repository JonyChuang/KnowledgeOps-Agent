"""Tests for the complete document-to-vector indexing workflow."""

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select

from knowledgeops.db import Database
from knowledgeops.models import DocumentChunk, DocumentStatus
from knowledgeops.rag import (
    DeterministicEmbeddingProvider,
    FakeKeywordStore,
    KeywordPoint,
    QdrantVectorStore,
)
from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate
from knowledgeops.services import DocumentIndexingService, KnowledgeService


class FailingKeywordStore(FakeKeywordStore):
    """Simulate an Elasticsearch write failure."""

    async def upsert_points(self, points: list[KeywordPoint]) -> None:
        raise RuntimeError("Elasticsearch write failed.")


@pytest.mark.asyncio
async def test_index_document_writes_vectors_and_marks_document_ready(tmp_path):
    """Successful vector storage should transition the document to ready."""
    database_path = (tmp_path / "full-indexing.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")
    qdrant_client = AsyncQdrantClient(location=":memory:")
    vector_store = QdrantVectorStore(
        qdrant_client,
        collection_name="full_indexing_test",
        dimensions=16,
    )
    embedding_provider = DeterministicEmbeddingProvider(dimensions=16)
    keyword_store = FakeKeywordStore()

    try:
        await database.create_schema()

        async for session in database.session():
            knowledge_service = KnowledgeService(session)
            knowledge_base = await knowledge_service.create_knowledge_base(
                KnowledgeBaseCreate(name="Full Indexing Handbook")
            )
            document = await knowledge_service.upload_text_document(
                knowledge_base.id,
                TextDocumentCreate(
                    source_name="guide.md",
                    content="A" * 900,
                ),
            )

            indexing_service = DocumentIndexingService(
                session,
                embedding_provider=embedding_provider,
                vector_store=vector_store,
                keyword_store=keyword_store,
            )
            indexed_document = await indexing_service.index_document(
                document.id,
                actor="worker-1",
            )

            assert indexed_document.status is DocumentStatus.READY
            assert indexed_document.chunk_count == 2

        async for session in database.session():

            result = await session.scalars(
                select(DocumentChunk).order_by(DocumentChunk.chunk_index)
            )
            chunks = list(result)


            assert {
                result.chunk_id
                for result in keyword_store.results
            } == {
                chunk.id
                for chunk in chunks
            }
            assert len(chunks) == 2
            assert all(chunk.vector_id is not None for chunk in chunks)
            assert all(
                chunk.embedding_model == "deterministic-test-v1"
                for chunk in chunks
            )

            payload = await vector_store.get_payload(chunks[0].vector_id)
            assert payload is not None
            assert payload["document_id"] == document.id
            assert payload["chunk_index"] == 0

    finally:
        await vector_store.close()
        await database.dispose()

@pytest.mark.asyncio
async def test_index_document_marks_failed_when_keyword_store_write_fails(tmp_path):
    """A document cannot become ready when Elasticsearch indexing fails."""
    database_path = (tmp_path / "keyword-store-failure.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")
    qdrant_client = AsyncQdrantClient(location=":memory:")
    vector_store = QdrantVectorStore(
        qdrant_client,
        collection_name="keyword_store_failure_test",
        dimensions=16,
    )

    try:
        await database.create_schema()

        async for session in database.session():
            knowledge_service = KnowledgeService(session)
            knowledge_base = await knowledge_service.create_knowledge_base(
                KnowledgeBaseCreate(name="Failure Handling Handbook")
            )
            document = await knowledge_service.upload_text_document(
                knowledge_base.id,
                TextDocumentCreate(
                    source_name="failure-guide.md",
                    content="Restart the API service.",
                ),
            )

            indexing_service = DocumentIndexingService(
                session,
                embedding_provider=DeterministicEmbeddingProvider(dimensions=16),
                vector_store=vector_store,
                keyword_store=FailingKeywordStore(),
            )
            indexed_document = await indexing_service.index_document(document.id)

            assert indexed_document.status is DocumentStatus.FAILED
            assert indexed_document.error_message == "Elasticsearch write failed."
    finally:
        await vector_store.close()
        await database.dispose()