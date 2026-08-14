"""Integration tests for KnowledgeOps knowledge-base HTTP endpoints."""


import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings
from knowledgeops.graphrag import GraphChunk
from knowledgeops.rag import HybridRetrievedChunk


@pytest.fixture
def client(tmp_path):
    """Provide an application backed by a fresh SQLite database per test."""
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    # API tests must not read the developer's real cloud credentials from .env.
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        auto_create_schema=True,
        auth_test_mode=True,

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


def test_index_document_endpoint_enqueues_celery_task(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_enqueue_document_index(
        document_id: str,
        *,
        actor: str,
    ) -> str:
        captured["document_id"] = document_id
        captured["actor"] = actor
        return "celery-task-001"

    monkeypatch.setattr(
        "knowledgeops.api.routers.knowledge_bases.enqueue_document_index",
        fake_enqueue_document_index,
    )

    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "API Indexing Handbook"},
    ).json()
    uploaded = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
        json={
            "source_name": "api-guide.md",
            "content": "Index this document through Celery.",
        },
    )

    document_id = uploaded.json()["id"]
    response = client.post(
        f"/api/v1/documents/{document_id}/index",
        headers={"X-Actor": "api-user"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "document_id": document_id,
        "task_id": "celery-task-001",
        "status": "queued",
    }
    assert captured == {
        "document_id": document_id,
        "actor": "api-user",
    }


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
    class FakeRetriever:
        """Return one fused result without real external services."""

        def __init__(self) -> None:
            self.knowledge_base_id = ""
            self.closed = False

        async def retrieve(self, query: str, *, knowledge_base_id: str, limit: int):
            assert query == "How do I restart the API?"
            assert knowledge_base_id == self.knowledge_base_id
            assert limit == 3

            return [
                HybridRetrievedChunk(
                    chunk_id="chunk-1",
                    score=0.91,
                    sources=("vector", "keyword"),
                    knowledge_base_id=knowledge_base_id,
                    document_id="document-1",
                    source_name="runbook.md",
                    source_type="markdown",
                    chunk_index=0,
                    start_char=0,
                    end_char=42,
                    rerank_score=1.0,
                    text="Restart the API after changing variables.",
                )
            ]

        async def close(self) -> None:
            self.closed = True

    fake_retriever = FakeRetriever()

    monkeypatch.setattr(
        "knowledgeops.api.routers.knowledge_bases.build_hybrid_retriever",
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
            "chunk_id": "chunk-1",
            "sources": ["vector", "keyword"],
            "score": 0.91,
            "document_id": "document-1",
            "source_name": "runbook.md",
            "source_type": "markdown",
            "chunk_index": 0,
            "start_char": 0,
            "end_char": 42,
            "rerank_score": 1.0,
            "text": "Restart the API after changing variables.",
        }
    ]
    assert fake_retriever.closed is True


def test_search_knowledge_base_rejects_unknown_knowledge_base(client: TestClient):
    """Search must not construct external clients for an unknown knowledge base."""
    response = client.post(
        "/api/v1/knowledge-bases/missing-id/search",
        json={"query": "How do I restart the API?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge base not found."


def test_graph_search_knowledge_base_returns_related_chunks(
    client: TestClient,
    monkeypatch,
) -> None:
    """Graph search should expose entity-related chunks through an API."""

    class FakeGraphStore:
        def __init__(self) -> None:
            self.closed = False
            self.request: dict[str, object] = {}

        async def find_chunks(
            self,
            *,
            knowledge_base_id: str,
            entity_keys: list[str],
            limit: int,
        ) -> list[GraphChunk]:
            self.request = {
                "knowledge_base_id": knowledge_base_id,
                "entity_keys": entity_keys,
                "limit": limit,
            }
            return [
                GraphChunk(
                    chunk_id="graph-chunk-1",
                    document_id="document-1",
                    knowledge_base_id=knowledge_base_id,
                    source_name="vpn-runbook.md",
                    chunk_index=0,
                    text="Check VPN account permissions and network access.",
                )
            ]

        async def close(self) -> None:
            self.closed = True

    fake_store = FakeGraphStore()
    monkeypatch.setattr(
        "knowledgeops.api.routers.knowledge_bases.build_neo4j_graph_store",
        lambda settings: fake_store,
    )

    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Graph Search Handbook"},
    ).json()

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/graph/search",
        json={"query": "How do I troubleshoot VPN?", "limit": 3},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "chunk_id": "graph-chunk-1",
            "document_id": "document-1",
            "knowledge_base_id": knowledge_base["id"],
            "source_name": "vpn-runbook.md",
            "chunk_index": 0,
            "text": "Check VPN account permissions and network access.",
        }
    ]
    assert fake_store.request == {
        "knowledge_base_id": knowledge_base["id"],
        "entity_keys": ["vpn"],
        "limit": 3,
    }
    assert fake_store.closed is True

def test_upload_local_file_document(client: TestClient):
    """A raw local-file upload should be extracted and stored for indexing."""
    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Local File Imports"},
    ).json()

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents/upload",
        params={"source_name": "runbook.md"},
        headers={"X-Actor": "file-user", "Content-Type": "text/markdown"},
        content=b"# VPN Runbook\nRestart the client after checking permissions.",
    )

    assert response.status_code == 201
    assert response.json()["source_name"] == "runbook.md"
    assert response.json()["source_type"] == "markdown"
    assert response.json()["status"] == "uploaded"


def test_upload_local_file_rejects_unsupported_extension(client: TestClient):
    """Binary file types outside the supported import list must be rejected."""
    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Unsupported File Imports"},
    ).json()

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents/upload",
        params={"source_name": "archive.exe"},
        content=b"not a supported source",
    )

    assert response.status_code == 422
    assert "Supported file types" in response.json()["detail"]


def test_import_webpage_document(client: TestClient, monkeypatch):
    """Web imports should reuse document persistence after safe fetching."""
    from knowledgeops.rag import ParsedDocument

    async def fake_import_web_page(url: str, *, max_bytes: int, timeout_seconds: float):
        assert url == "https://example.com/runbook"
        assert max_bytes > 0
        assert timeout_seconds > 0
        return ParsedDocument(
            text="Restart the VPN client after checking permissions.",
            source_name="Example Runbook",
            source_type="web",
            metadata={"source_url": url},
        )

    monkeypatch.setattr(
        "knowledgeops.api.routers.knowledge_bases.import_web_page",
        fake_import_web_page,
    )
    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Web Imports"},
    ).json()

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents/web-import",
        headers={"X-Actor": "web-user"},
        json={"url": "https://example.com/runbook"},
    )

    assert response.status_code == 201
    assert response.json()["source_name"] == "Example Runbook"
    assert response.json()["source_type"] == "web"
