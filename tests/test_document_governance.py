"""Tests for enterprise document availability and evidence diversity."""

from dataclasses import dataclass

import pytest
from sqlalchemy import select

from knowledgeops.db import Database
from knowledgeops.models import AuditEvent, DocumentLifecycle, DocumentStatus
from knowledgeops.rag import (
    HybridRetriever,
    KeywordSearchResult,
    VectorSearchResult,
)
from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate
from knowledgeops.services import KnowledgeService


@dataclass
class StaticSemanticRetriever:
    """Return fixed recall candidates without invoking an embedding model."""

    results: list[VectorSearchResult]

    async def retrieve_vector_results(self, *args, **kwargs) -> list[VectorSearchResult]:
        return self.results


@dataclass
class StaticKeywordStore:
    """Return fixed keyword candidates for hybrid orchestration tests."""

    results: list[KeywordSearchResult]

    async def search(self, *args, **kwargs) -> list[KeywordSearchResult]:
        return self.results

    async def close(self) -> None:
        return None


@dataclass
class RecordingVectorStore:
    updates: list[dict[str, str]]

    async def update_document_lifecycle(self, **kwargs) -> None:
        self.updates.append(kwargs)


@dataclass
class RecordingKeywordStore:
    updates: list[dict[str, str]]

    async def update_document_lifecycle(self, **kwargs) -> None:
        self.updates.append(kwargs)


def _payload(document_id: str, lifecycle: str = "active") -> dict[str, object]:
    return {
        "knowledge_base_id": "support",
        "document_id": document_id,
        "source_name": f"{document_id}.md",
        "source_type": "markdown",
        "document_lifecycle": lifecycle,
        "chunk_index": 0,
        "start_char": 0,
        "end_char": 10,
        "text": "VPN access procedure",
    }


@pytest.mark.asyncio
async def test_hybrid_retrieval_excludes_archived_sources_and_keeps_diverse_evidence():
    """Normal searches should not cite archived policy or one source three times."""
    candidates = [
        ("a1", "current-policy", "active"),
        ("a2", "current-policy", "active"),
        ("a3", "current-policy", "active"),
        ("b1", "vpn-runbook", "active"),
        ("c1", "retired-policy", "archived"),
    ]
    vector_results = [
        VectorSearchResult(chunk_id, 1.0, _payload(document_id, lifecycle))
        for chunk_id, document_id, lifecycle in candidates
    ]
    keyword_results = [
        KeywordSearchResult(chunk_id, 1.0, _payload(document_id, lifecycle))
        for chunk_id, document_id, lifecycle in candidates
    ]
    retriever = HybridRetriever(
        semantic_retriever=StaticSemanticRetriever(vector_results),
        keyword_store=StaticKeywordStore(keyword_results),
        candidate_limit=10,
        max_chunks_per_document=2,
    )

    results = await retriever.retrieve(
        "VPN access",
        knowledge_base_id="support",
        limit=3,
    )

    assert [result.chunk_id for result in results] == ["a1", "a2", "b1"]
    assert all(result.lifecycle == "active" for result in results)

    historical_results = await retriever.retrieve(
        "VPN access",
        knowledge_base_id="support",
        limit=5,
        include_archived=True,
    )
    assert {result.chunk_id for result in historical_results} >= {"c1"}


@pytest.mark.asyncio
async def test_archiving_ready_document_updates_index_metadata_and_audit(tmp_path):
    """Archiving changes availability without asking the worker to re-embed text."""
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'governance.db').as_posix()}")
    vector_store = RecordingVectorStore([])
    keyword_store = RecordingKeywordStore([])
    try:
        await database.create_schema()
        async for session in database.session():
            service = KnowledgeService(session)
            knowledge_base = await service.create_knowledge_base(
                KnowledgeBaseCreate(name="Governance Handbook")
            )
            document = await service.upload_text_document(
                knowledge_base.id,
                TextDocumentCreate(source_name="policy.md", content="Current policy."),
            )
            document.status = DocumentStatus.READY
            await session.commit()

            updated = await service.update_document_lifecycle(
                document.id,
                DocumentLifecycle.ARCHIVED,
                actor="policy-owner",
                vector_store=vector_store,
                keyword_store=keyword_store,
            )

            assert updated.lifecycle is DocumentLifecycle.ARCHIVED
            assert vector_store.updates[0]["lifecycle"] == "archived"
            assert keyword_store.updates[0]["document_id"] == document.id

        async for session in database.session():
            event = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.event_type == "document.lifecycle_changed"
                )
            )
            assert event is not None
            assert event.payload["from"] == "active"
            assert event.payload["to"] == "archived"
    finally:
        await database.dispose()
