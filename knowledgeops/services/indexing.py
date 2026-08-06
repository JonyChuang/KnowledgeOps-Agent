"""Business workflow for preparing source documents for vector indexing."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEvent, Document, DocumentChunk, DocumentStatus
from ..rag import parse_text_document, split_text
from ..repositories import (
    AuditEventRepository,
    DocumentChunkRepository,
    DocumentRepository,
)
from .knowledge import ResourceNotFoundError


class DocumentIndexingService:
    """Parse, split, and persist chunks before embedding generation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.documents = DocumentRepository(session)
        self.chunks = DocumentChunkRepository(session)
        self.audit_events = AuditEventRepository(session)

    async def prepare_document_chunks(
        self,
        document_id: str,
        *,
        actor: str = "system",
        chunk_size: int = 800,
        overlap: int = 120,
    ) -> Document:
        """Create persistent chunks and leave the document ready for embedding."""
        document = await self.documents.get(document_id)
        if document is None:
            raise ResourceNotFoundError("Document not found.")

        # The document has entered the wider indexing workflow.
        document.status = DocumentStatus.INDEXING
        document.error_message = None

        try:
            parsed_document = parse_text_document(
                document.content,
                document.source_name,
                document.source_type,
            )
            text_chunks = split_text(
                parsed_document.text,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        except (TypeError, ValueError) as error:
            # Parsing failures must be visible through the document-status API.
            document.status = DocumentStatus.FAILED
            document.error_message = str(error)
            await self.session.commit()
            await self.session.refresh(document)
            return document

        persistent_chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
            )
            for chunk in text_chunks
        ]

        # Reprocessing replaces old derived chunks instead of creating duplicates.
        await self.chunks.replace_for_document(document.id, persistent_chunks)
        document.chunk_count = len(persistent_chunks)

        await self.audit_events.create(
            AuditEvent(
                event_type="document.chunked",
                actor=actor,
                entity_type="document",
                entity_id=document.id,
                payload={
                    "chunk_count": document.chunk_count,
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(document)

        return document