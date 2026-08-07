"""Tests for the complete document-to-vector indexing workflow."""

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select

from knowledgeops.db import Database
from knowledgeops.models import DocumentChunk, DocumentStatus
from knowledgeops.rag import (
    DeterministicEmbeddingProvider,
    QdrantVectorStore,
)
from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate
from knowledgeops.services import DocumentIndexingService, KnowledgeService


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