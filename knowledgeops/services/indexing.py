"""Business workflow for preparing source documents for vector indexing."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEvent, Document, DocumentChunk, DocumentStatus
from ..rag import EmbeddingProvider, QdrantVectorStore, VectorPoint, parse_text_document, split_text
from ..repositories import (
    AuditEventRepository,
    DocumentChunkRepository,
    DocumentRepository,
)
from .knowledge import ResourceNotFoundError


class DocumentIndexingService:
    """Parse, split, and persist chunks before embedding generation."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: QdrantVectorStore | None = None,
    ):
        self.session = session
        self.documents = DocumentRepository(session)
        self.chunks = DocumentChunkRepository(session)
        self.audit_events = AuditEventRepository(session)
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

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

    async def index_document(
        self,
        document_id: str,
        *,
        actor: str = "system",
    ) -> Document:
        """Embed stored chunks, write vectors, and finalize document indexing."""
        if self.embedding_provider is None or self.vector_store is None:
            raise RuntimeError(
                "Embedding provider and vector store are required for indexing."
            )

        document = await self.prepare_document_chunks(
            document_id,
            actor=actor,
        )

        # Parsing failures are already persisted by the preparation step.
        if document.status is DocumentStatus.FAILED:
            return document

        try:
            stored_chunks = await self.chunks.list_for_document(document.id)
            texts = [chunk.text for chunk in stored_chunks]
            vectors = await self.embedding_provider.embed_texts(texts)

            if len(vectors) != len(stored_chunks):
                raise ValueError("Embedding count does not match chunk count.")

            points = [
                VectorPoint(
                    # The database Chunk UUID is also the stable Qdrant point ID.
                    vector_id=chunk.id,
                    vector=vector,
                    payload={
                        "knowledge_base_id": document.knowledge_base_id,
                        "document_id": document.id,
                        "source_name": document.source_name,
                        "source_type": document.source_type,
                        "chunk_index": chunk.chunk_index,
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char,
                        "text": chunk.text,
                    },
                )
                for chunk, vector in zip(stored_chunks, vectors)
            ]

            await self.vector_store.upsert_points(points)

            # Only mark chunks indexed after Qdrant confirms the write.
            for chunk in stored_chunks:
                chunk.vector_id = chunk.id
                chunk.embedding_model = self.embedding_provider.model_name

            document.status = DocumentStatus.READY
            document.error_message = None

            await self.audit_events.create(
                AuditEvent(
                    event_type="document.indexed",
                    actor=actor,
                    entity_type="document",
                    entity_id=document.id,
                    payload={
                        "chunk_count": len(stored_chunks),
                        "embedding_model": self.embedding_provider.model_name,
                    },
                )
            )

            await self.session.commit()
            await self.session.refresh(document)
            return document

        except Exception as error:
            # Re-read after rollback so the failure state is persisted cleanly.
            await self.session.rollback()
            failed_document = await self.documents.get(document_id)

            if failed_document is None:
                raise ResourceNotFoundError("Document not found.") from error

            failed_document.status = DocumentStatus.FAILED
            failed_document.error_message = str(error)
            await self.session.commit()
            await self.session.refresh(failed_document)

            return failed_document