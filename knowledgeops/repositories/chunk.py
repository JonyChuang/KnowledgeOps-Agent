"""Database access operations for persistent document chunks."""

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DocumentChunk


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