"""Business-rule tests for KnowledgeOps knowledge services."""

import pytest
from sqlalchemy import select

from knowledgeops.db import Database
from knowledgeops.models import AuditEvent
from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate
from knowledgeops.services import KnowledgeService, ResourceConflictError


@pytest.mark.asyncio
async def test_service_creates_knowledge_base_and_document(tmp_path):
    """Creation should persist data and emit audit events."""
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        await database.create_schema()

        async for session in database.session():
            service = KnowledgeService(session)
            knowledge_base = await service.create_knowledge_base(
                KnowledgeBaseCreate(name="Support Handbook"),
                actor="alice",
            )
            document = await service.upload_text_document(
                knowledge_base.id,
                TextDocumentCreate(
                    source_name="faq.md",
                    content="Restart the service after changing configuration.",
                ),
                actor="alice",
            )

        async for session in database.session():
            service = KnowledgeService(session)
            documents = await service.list_documents(knowledge_base.id)
            event = await session.scalar(select(AuditEvent).order_by(AuditEvent.created_at.desc()))

            assert len(documents) == 1
            assert documents[0].id == document.id
            assert event is not None
            assert event.event_type == "document.uploaded"
            assert "content" not in event.payload
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_service_rejects_duplicate_document_content(tmp_path):
    """The same content should not create duplicate index work."""
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        await database.create_schema()

        async for session in database.session():
            service = KnowledgeService(session)
            knowledge_base = await service.create_knowledge_base(
                KnowledgeBaseCreate(name="Security Handbook")
            )
            payload = TextDocumentCreate(
                source_name="policy.md",
                content="Use MFA for all production accounts.",
            )

            await service.upload_text_document(knowledge_base.id, payload)

            with pytest.raises(ResourceConflictError):
                await service.upload_text_document(knowledge_base.id, payload)
    finally:
        await database.dispose()