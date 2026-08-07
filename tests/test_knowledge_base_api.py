"""Integration tests for KnowledgeOps knowledge-base HTTP endpoints."""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings
from knowledgeops.models import DocumentStatus
from knowledgeops.rag import RetrievedChunk
from knowledgeops.repositories import DocumentRepository


@pytest.fixture
def client(tmp_path):
    """Provide an application backed by a fresh SQLite database per test."""
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    # API tests must not read the developer's real cloud credentials from .env.
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        auto_create_schema=True,

        # Explicit test values override any Qdrant variables in the terminal.
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
    )

    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_create_and_list_knowledge_bases(client: TestClient):
    """Created knowledge bases should appear in the management list."""
    created = client.post(
        "/api/v1/knowledge-bases",
        headers={"X-Actor": "alice"},
        json={
            "name": "Product Support",
            "description": "Support playbooks and FAQs.",
            "department": "support",
        },
    )

    assert created.status_code == 201
    assert created.json()["name"] == "Product Support"

    listed = client.get("/api/v1/knowledge-bases")

    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_upload_document_and_query_status(client: TestClient):
    """Document upload should expose metadata and the uploaded lifecycle state."""
    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Engineering Docs"},
    ).json()

    uploaded = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
        headers={"X-Actor": "bob"},
        json={
            "source_name": "runbook.md",
            "content": "Restart the API after changing environment variables.",
        },
    )

    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "uploaded"
    assert "content" not in uploaded.json()

    document_id = uploaded.json()["id"]
    status_response = client.get(f"/api/v1/documents/{document_id}")

    assert status_response.status_code == 200
    assert status_response.json()["source_name"] == "runbook.md"


def test_upload_document_rejects_unknown_knowledge_base(client: TestClient):
    """Document ingestion must not create orphan rows."""
    response = client.post(
        "/api/v1/knowledge-bases/missing-id/documents",
        json={"source_name": "faq.md", "content": "Example content."},
    )

    assert response.status_code == 404


def test_index_document_endpoint_delegates_to_task(client: TestClient, monkeypatch):
    """The API should pass the document and runtime dependencies to the task."""

    async def fake_index_document(
        document_id: str,
        *,
        database,
        settings,
        actor: str,
    ):
        """Use the real database but avoid external Embedding and Qdrant calls."""
        assert settings.qdrant_url == "http://localhost:6333"
        assert actor == "api-user"

        async for session in database.session():
            document = await DocumentRepository(session).get(document_id)
            assert document is not None

            # Simulate the successful result returned by the real task.
            document.status = DocumentStatus.READY
            document.chunk_count = 2
            await session.commit()
            await session.refresh(document)
            return document

        raise RuntimeError("Database session context did not yield a session.")

    monkeypatch.setattr(
        "knowledgeops.api.routers.knowledge_bases.index_document",
        fake_index_document,
    )

    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "API Indexing Handbook"},
    ).json()

    uploaded = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
        json={
            "source_name": "api-guide.md",
            "content": "Index this document through the API.",
        },
    )

    document_id = uploaded.json()["id"]

    response = client.post(
        f"/api/v1/documents/{document_id}/index",
        headers={"X-Actor": "api-user"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["chunk_count"] == 2


def test_index_document_endpoint_rejects_unknown_document(client: TestClient):
    """An unknown document should be rejected before external clients are created."""
    response = client.post("/api/v1/documents/missing-id/index")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."


def test_search_knowledge_base_returns_citable_results(
    client: TestClient,
    monkeypatch,
):
    """The search API should return retriever results through its response schema."""

    @dataclass
    class FakeVectorStore:
        """Record close calls without constructing a Qdrant client."""

        closed: bool = False

        async def close(self) -> None:
            self.closed = True

    class FakeRetriever:
        """Replace real OpenAI and Qdrant calls with a deterministic result."""

        def __init__(self) -> None:
            self.vector_store = FakeVectorStore()

        async def retrieve(
            self,
            query: str,
            *,
            knowledge_base_id: str,
            limit: int,
        ) -> list[RetrievedChunk]:
            assert query == "How do I restart the API?"
            assert knowledge_base_id == self.knowledge_base_id
            assert limit == 3

            return [
                RetrievedChunk(
                    vector_id="chunk-vector-1",
                    score=0.91,
                    knowledge_base_id=knowledge_base_id,
                    document_id="document-1",
                    source_name="runbook.md",
                    source_type="markdown",
                    chunk_index=0,
                    start_char=0,
                    end_char=42,
                    text="Restart the API after changing variables.",
                )
            ]

    fake_retriever = FakeRetriever()

    monkeypatch.setattr(
        "knowledgeops.api.routers.knowledge_bases.build_semantic_retriever",
        lambda settings: fake_retriever,
    )

    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Search API Handbook"},
    ).json()
    fake_retriever.knowledge_base_id = knowledge_base["id"]

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/search",
        json={
            "query": "How do I restart the API?",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "vector_id": "chunk-vector-1",
            "score": 0.91,
            "document_id": "document-1",
            "source_name": "runbook.md",
            "source_type": "markdown",
            "chunk_index": 0,
            "start_char": 0,
            "end_char": 42,
            "text": "Restart the API after changing variables.",
        }
    ]
    assert fake_retriever.vector_store.closed is True


def test_search_knowledge_base_rejects_unknown_knowledge_base(client: TestClient):
    """Search must not construct external clients for an unknown knowledge base."""
    response = client.post(
        "/api/v1/knowledge-bases/missing-id/search",
        json={"query": "How do I restart the API?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge base not found."