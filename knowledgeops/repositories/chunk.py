"""Database access operations for persistent document chunks."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Document, DocumentChunk, DocumentStatus


@dataclass(frozen=True)
class ReadyDocumentChunk:
    """A citable chunk from an indexed document in one knowledge base."""

    id: str
    document_id: str
    source_name: str
    source_type: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str


class DocumentChunkRepository:
    """Read and replace chunks without owning the database transaction."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def replace_for_document(
        self,
        document_id: str,
        chunks: Sequence[DocumentChunk],
    ) -> list[DocumentChunk]:
        """Replace all derived chunks when a document is processed again."""
        # Re-indexing must not leave old chunks mixed with new chunks.
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )

        stored_chunks = list(chunks)
        self.session.add_all(stored_chunks)
        await self.session.flush()

        return stored_chunks

    async def list_for_document(self, document_id: str) -> list[DocumentChunk]:
        """Return chunks in original-document order."""
        result = await self.session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result)

    async def list_ready_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 3,
    ) -> list[ReadyDocumentChunk]:
        """Return a small citable sample of a knowledge base's ready content.

        This is intentionally not a search result. It lets the Agent explain
        the corpus scope when a user's query has no direct retrieval match.
        """
        result = await self.session.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.knowledge_base_id == knowledge_base_id,
                Document.status == DocumentStatus.READY,
            )
            .order_by(Document.updated_at.desc(), DocumentChunk.chunk_index)
            .limit(limit)
        )
        return [
            ReadyDocumentChunk(
                id=chunk.id,
                document_id=document.id,
                source_name=document.source_name,
                source_type=document.source_type,
                chunk_index=chunk.chunk_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                text=chunk.text,
            )
            for chunk, document in result.all()
        ]
