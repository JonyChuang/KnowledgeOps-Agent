"""Tests for KnowledgeOps repository behavior using temporary SQLite."""

import pytest

from knowledgeops.db import Database
from knowledgeops.models import AuditEvent, Document
from knowledgeops.repositories import (
    AuditEventRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
)


@pytest.mark.asyncio
async def test_repositories_persist_knowledge_base_and_document(tmp_path):
    """Repositories should write related records in one transaction."""
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        await database.create_schema()

        async for session in database.session():
            knowledge_bases = KnowledgeBaseRepository(session)
            documents = DocumentRepository(session)
            audit_events = AuditEventRepository(session)

            knowledge_base = await knowledge_bases.create(
                name="Operations Handbook",
                description="Support procedures for internal teams.",
                department="operations",
            )
            document = await documents.create(
                Document(
                    knowledge_base_id=knowledge_base.id,
                    source_name="incident-guide.md",
                    content="Escalate production incidents to the on-call engineer.",
                    checksum="b" * 64,
                )
            )
            await audit_events.create(
                AuditEvent(
                    event_type="document.uploaded",
                    actor="test-user",
                    entity_type="document",
                    entity_id=document.id,
                    payload={"source_name": document.source_name},
                )
            )
            await session.commit()

        async for session in database.session():
            knowledge_bases = KnowledgeBaseRepository(session)
            documents = DocumentRepository(session)

            stored_base = await knowledge_bases.get(knowledge_base.id)
            stored_documents = await documents.list_for_knowledge_base(
                knowledge_base.id
            )

            assert stored_base is not None
            assert stored_base.name == "Operations Handbook"
            assert len(stored_documents) == 1
            assert stored_documents[0].source_name == "incident-guide.md"
    finally:
        await database.dispose()