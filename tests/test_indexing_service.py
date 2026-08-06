"""Tests for the document chunking business workflow."""

import pytest
from sqlalchemy import select

from knowledgeops.db import Database
from knowledgeops.models import AuditEvent, Document, DocumentStatus
from knowledgeops.repositories import DocumentChunkRepository
from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate
from knowledgeops.services import DocumentIndexingService, KnowledgeService


@pytest.mark.asyncio
async def test_indexing_service_persists_chunks_and_updates_status(tmp_path):
    """Uploaded documents should become chunked documents awaiting embeddings."""
    database_path = (tmp_path / "indexing.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        await database.create_schema()

        async for session in database.session():
            knowledge_service = KnowledgeService(session)
            knowledge_base = await knowledge_service.create_knowledge_base(
                KnowledgeBaseCreate(name="Indexing Handbook")
            )
            document = await knowledge_service.upload_text_document(
                knowledge_base.id,
                TextDocumentCreate(
                    source_name="runbook.md",
                    content="A" * 900,
                ),
            )

            indexing_service = DocumentIndexingService(session)
            indexed_document = await indexing_service.prepare_document_chunks(
                document.id,
                actor="worker-1",
            )

            assert indexed_document.status is DocumentStatus.INDEXING
            assert indexed_document.chunk_count == 2

        async for session in database.session():
            stored_document = await session.get(Document, document.id)
            chunks = await DocumentChunkRepository(session).list_for_document(
                document.id
            )
            event = await session.scalar(
                select(AuditEvent)
                .where(AuditEvent.event_type == "document.chunked")
                .order_by(AuditEvent.created_at.desc())
            )

            assert stored_document is not None
            assert stored_document.status is DocumentStatus.INDEXING
            assert len(chunks) == 2
            assert chunks[0].text == "A" * 800
            assert chunks[1].start_char == 680
            assert event is not None
            assert event.payload["chunk_count"] == 2
            assert event.actor == "worker-1"

    finally:
        await database.dispose()