"""Business rules for knowledge bases and text document uploads."""

from __future__ import annotations

import hashlib

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEvent, Document, DocumentStatus, KnowledgeBase
from ..repositories import (
    AuditEventRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
)
from ..schemas import KnowledgeBaseCreate, TextDocumentCreate


class ResourceNotFoundError(LookupError):
    """Raised when a requested business entity does not exist."""


class ResourceConflictError(ValueError):
    """Raised when a write violates a business uniqueness constraint."""


class KnowledgeService:
    """Coordinate repositories, transactions, audit records, and business rules."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.documents = DocumentRepository(session)
        self.audit_events = AuditEventRepository(session)

    async def create_knowledge_base(
        self,
        payload: KnowledgeBaseCreate,
        *,
        actor: str = "anonymous",
    ) -> KnowledgeBase:
        """Create a knowledge base and record its creation as an audit event."""
        try:
            knowledge_base = await self.knowledge_bases.create(
                **payload.model_dump()
            )
            await self.audit_events.create(
                AuditEvent(
                    event_type="knowledge_base.created",
                    actor=actor,
                    entity_type="knowledge_base",
                    entity_id=knowledge_base.id,
                    payload={"department": knowledge_base.department},
                )
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ResourceConflictError(
                "A knowledge base with this name already exists."
            ) from error

        await self.session.refresh(knowledge_base)
        return knowledge_base

    async def list_knowledge_bases(self) -> list[KnowledgeBase]:
        """Return knowledge bases for the future management interface."""
        return await self.knowledge_bases.list()

    async def upload_text_document(
        self,
        knowledge_base_id: str,
        payload: TextDocumentCreate,
        *,
        actor: str = "anonymous",
    ) -> Document:
        """Persist a text document before the later indexing task processes it."""
        await self._require_knowledge_base(knowledge_base_id)

        # Hashes support idempotency without storing duplicate source content.
        checksum = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()

        try:
            document = await self.documents.create(
                Document(
                    knowledge_base_id=knowledge_base_id,
                    source_name=payload.source_name,
                    source_type=payload.source_type,
                    content=payload.content,
                    checksum=checksum,
                    status=DocumentStatus.UPLOADED,
                )
            )
            await self.audit_events.create(
                AuditEvent(
                    event_type="document.uploaded",
                    actor=actor,
                    entity_type="document",
                    entity_id=document.id,
                    # Never store raw document content in audit metadata.
                    payload={
                        "source_name": document.source_name,
                        "source_type": document.source_type,
                        "checksum": checksum,
                    },
                )
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ResourceConflictError(
                "This document content already exists in the knowledge base."
            ) from error

        await self.session.refresh(document)
        return document

    async def list_documents(self, knowledge_base_id: str) -> list[Document]:
        """List document metadata after validating the parent knowledge base."""
        await self._require_knowledge_base(knowledge_base_id)
        return await self.documents.list_for_knowledge_base(knowledge_base_id)

    async def get_document(self, document_id: str) -> Document:
        """Return a document and its current indexing status."""
        document = await self.documents.get(document_id)
        if document is None:
            raise ResourceNotFoundError("Document not found.")
        return document

    async def _require_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBase:
        """Centralize the not-found rule used by document operations."""
        knowledge_base = await self.knowledge_bases.get(knowledge_base_id)
        if knowledge_base is None:
            raise ResourceNotFoundError("Knowledge base not found.")
        return knowledge_base