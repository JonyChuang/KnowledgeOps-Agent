"""Persistence tests for document chunks."""

import pytest
from sqlalchemy import select

from knowledgeops.db import Database
from knowledgeops.models import Document, DocumentChunk, KnowledgeBase


@pytest.mark.asyncio
async def test_document_chunks_persist_with_source_document(tmp_path):
    """A chunk should persist and remain linked to its source document."""
    # Use an isolated SQLite file for this test.
    database_path = (tmp_path / "chunks.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        # Create the current schema for the isolated test database.
        await database.create_schema()

        async for session in database.session():
            knowledge_base = KnowledgeBase(
                name="Chunk Test Knowledge Base",
                description="Test data",
                department="engineering",
            )
            session.add(knowledge_base)
            await session.flush()

            document = Document(
                knowledge_base_id=knowledge_base.id,
                source_name="guide.md",
                content="A long source document.",
                checksum="b" * 64,
            )
            session.add(document)
            await session.flush()

            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                text="A long source",
                start_char=0,
                end_char=13,
            )
            session.add(chunk)
            await session.commit()

        # Read the chunk from a new session to verify real persistence.
        async for session in database.session():
            stored_chunk = await session.scalar(select(DocumentChunk))

            assert stored_chunk is not None
            assert stored_chunk.document_id == document.id
            assert stored_chunk.chunk_index == 0
            assert stored_chunk.text == "A long source"
            assert stored_chunk.vector_id is None

    finally:
        # Release the engine so Windows can remove the temporary SQLite file.
        await database.dispose()