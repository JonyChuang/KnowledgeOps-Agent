"""Persistence tests for the KnowledgeOps domain models."""

import pytest
from sqlalchemy import select

from knowledgeops.db import Database
from knowledgeops.models import AuditEvent, Document, DocumentStatus, KnowledgeBase


@pytest.mark.asyncio
async def test_knowledge_models_persist_to_sqlite(tmp_path):
    """A knowledge base, document, and audit event should survive a commit."""
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        await database.create_schema()

        async for session in database.session():
            knowledge_base = KnowledgeBase(
                name="Engineering Handbook",
                description="Internal engineering procedures.",
                department="engineering",
            )
            session.add(knowledge_base)
            await session.flush()  # Generate the UUID before linking child records.

            document = Document(
                knowledge_base_id=knowledge_base.id,
                source_name="deployment-guide.md",
                content="Deploy the service with Docker Compose.",
                checksum="a" * 64,
            )
            event = AuditEvent(
                event_type="knowledge_base.created",
                actor="test-user",
                entity_type="knowledge_base",
                entity_id=knowledge_base.id,
                payload={"department": "engineering"},
            )
            session.add_all([document, event])
            await session.commit()

        async for session in database.session():
            stored_document = await session.scalar(select(Document))
            stored_event = await session.scalar(select(AuditEvent))

            assert stored_document is not None
            assert stored_document.status is DocumentStatus.UPLOADED
            assert stored_document.chunk_count == 0
            assert stored_event is not None
            assert stored_event.payload["department"] == "engineering"
    finally:
        await database.dispose()