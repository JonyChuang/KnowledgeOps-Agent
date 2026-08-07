"""Tests for the document-indexing task entry point."""

import pytest
from qdrant_client import AsyncQdrantClient

from knowledgeops.config import Settings
from knowledgeops.db import Database
from knowledgeops.models import DocumentStatus
from knowledgeops.rag import DeterministicEmbeddingProvider, QdrantVectorStore
from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate
from knowledgeops.services import KnowledgeService
from knowledgeops.tasks import index_document
from knowledgeops.tasks.indexing import build_qdrant_vector_store


def test_build_qdrant_vector_store_reads_settings(monkeypatch):
    """The runtime adapter must use Qdrant values from central configuration."""
    captured: dict[str, str | None] = {}

    class FakeQdrantClient:
        """Record constructor input without opening a real network connection."""

        def __init__(
            self,
            *,
            url: str,
            api_key: str | None = None,
        ) -> None:
            # Capture configuration without creating a real network client.
            captured["url"] = url
            captured["api_key"] = api_key

    monkeypatch.setattr(
        "knowledgeops.tasks.indexing.AsyncQdrantClient",
        FakeQdrantClient,
    )

    settings = Settings(
        qdrant_url="http://qdrant.example:6333",
        qdrant_collection="task_test_chunks",
        embedding_dimensions=16,
        qdrant_api_key="unit-test-qdrant-key",
    )

    vector_store = build_qdrant_vector_store(settings)

    assert captured["url"] == "http://qdrant.example:6333"
    assert vector_store.collection_name == "task_test_chunks"
    assert vector_store.dimensions == 16
    assert captured["api_key"] == "unit-test-qdrant-key"


@pytest.mark.asyncio
async def test_index_document_task_accepts_test_dependencies(tmp_path):
    """Injected dependencies let the task run without OpenAI or Qdrant services."""
    database_path = (tmp_path / "indexing-task.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")
    qdrant_client = AsyncQdrantClient(location=":memory:")
    vector_store = QdrantVectorStore(
        qdrant_client,
        collection_name="indexing_task_test",
        dimensions=16,
    )
    settings = Settings(
        qdrant_collection="indexing_task_test",
        embedding_dimensions=16,
    )

    try:
        await database.create_schema()

        async for session in database.session():
            knowledge_service = KnowledgeService(session)
            knowledge_base = await knowledge_service.create_knowledge_base(
                KnowledgeBaseCreate(name="Task Indexing Handbook")
            )
            document = await knowledge_service.upload_text_document(
                knowledge_base.id,
                TextDocumentCreate(
                    source_name="task-guide.md",
                    content="A" * 900,
                ),
            )

        indexed_document = await index_document(
            document.id,
            database=database,
            settings=settings,
            actor="test-worker",
            embedding_provider=DeterministicEmbeddingProvider(dimensions=16),
            vector_store=vector_store,
        )

        assert indexed_document.status is DocumentStatus.READY
        assert indexed_document.chunk_count == 2
    finally:
        await vector_store.close()
        await database.dispose()