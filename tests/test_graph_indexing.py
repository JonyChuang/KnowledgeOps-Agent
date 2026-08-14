"""Tests for GraphRAG enrichment during document indexing."""

import pytest
from qdrant_client import AsyncQdrantClient

from knowledgeops.db import Database
from knowledgeops.graphrag import InMemoryGraphStore, RuleBasedEntityExtractor
from knowledgeops.models import DocumentStatus
from knowledgeops.rag import (
    DeterministicEmbeddingProvider,
    FakeKeywordStore,
    QdrantVectorStore,
)
from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate
from knowledgeops.services import DocumentIndexingService, KnowledgeService


@pytest.mark.asyncio
async def test_indexing_writes_extracted_entities_to_the_graph(tmp_path) -> None:
    database_path = (tmp_path / "graph-indexing.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")
    qdrant_client = AsyncQdrantClient(location=":memory:")
    vector_store = QdrantVectorStore(
        qdrant_client,
        collection_name="graph_indexing_test",
        dimensions=8,
    )
    graph_store = InMemoryGraphStore()

    try:
        await database.create_schema()

        async for session in database.session():
            knowledge_service = KnowledgeService(session)
            knowledge_base = await knowledge_service.create_knowledge_base(
                KnowledgeBaseCreate(name="Graph Indexing Handbook")
            )
            document = await knowledge_service.upload_text_document(
                knowledge_base.id,
                TextDocumentCreate(
                    source_name="vpn-runbook.md",
                    content=(
                        "VPN connection failures require account permission "
                        "checks and network diagnostics."
                    ),
                ),
            )

            indexing_service = DocumentIndexingService(
                session,
                embedding_provider=DeterministicEmbeddingProvider(dimensions=8),
                vector_store=vector_store,
                keyword_store=FakeKeywordStore(),
                graph_store=graph_store,
                entity_extractor=RuleBasedEntityExtractor(
                    entity_names=["VPN", "account", "network"]
                ),
            )
            indexed_document = await indexing_service.index_document(document.id)

        related_chunks = await graph_store.find_chunks(
            knowledge_base_id=knowledge_base.id,
            entity_keys=["vpn", "network"],
            limit=5,
        )

        assert indexed_document.status is DocumentStatus.READY
        assert [chunk.source_name for chunk in related_chunks] == [
            "vpn-runbook.md"
        ]
    finally:
        await vector_store.close()
        await database.dispose()