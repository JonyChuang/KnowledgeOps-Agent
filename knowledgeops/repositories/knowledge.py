"""Database access objects for knowledge bases, documents, and audit events."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEvent, Document, KnowledgeBase


class KnowledgeBaseRepository:
    """Read and write knowledge-base rows without owning transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        name: str,
        description: str,
        department: str,
    ) -> KnowledgeBase:
        # Services decide when to commit so multiple writes stay atomic.
        knowledge_base = KnowledgeBase(
            name=name,
            description=description,
            department=department,
        )
        self.session.add(knowledge_base)
        await self.session.flush()
        return knowledge_base

    async def get(self, knowledge_base_id: str) -> KnowledgeBase | None:
        """Fetch one knowledge base by its public UUID."""
        return await self.session.get(KnowledgeBase, knowledge_base_id)

    async def list(self) -> list[KnowledgeBase]:
        """Return newest knowledge bases first for the future management UI."""
        result = await self.session.scalars(
            select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
        )
        return list(result)


class DocumentRepository:
    """Read and write raw source documents before RAG indexing."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document

    async def get(self, document_id: str) -> Document | None:
        """Used by the document-status API in the next substage."""
        return await self.session.get(Document, document_id)

    async def list_for_knowledge_base(
        self,
        knowledge_base_id: str,
    ) -> list[Document]:
        result = await self.session.scalars(
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at.desc())
        )
        return list(result)


class AuditEventRepository:
    """Append audit records; business events must not be silently discarded."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: AuditEvent) -> AuditEvent:
        self.session.add(event)
        await self.session.flush()
        return event