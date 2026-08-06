"""Integration tests for KnowledgeOps knowledge-base HTTP endpoints."""

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings


@pytest.fixture
def client(tmp_path):
    """Provide an application backed by a fresh SQLite database per test."""
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database_path}",
        auto_create_schema=True,
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