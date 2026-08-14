"""Integration tests for the employee workbench endpoint."""

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings


@pytest.fixture
def client(tmp_path):
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        auto_create_schema=True,
        auth_test_mode=True,
        chat_model=None,
        chat_api_key=None,
        chat_base_url=None,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def create_ticket_through_agent(client: TestClient, actor: str) -> str:
    initial = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": actor},
        json={"user_message": "请帮我创建一个 VPN 无法连接的工单"},
    )
    assert initial.status_code == 201
    confirmation = client.post(
        f"/api/v1/agent/turns/{initial.json()['thread_id']}/confirmation",
        headers={"X-Actor": actor},
        json={"approved": True},
    )
    assert confirmation.status_code == 200
    return confirmation.json()["created_ticket_id"]


def test_dashboard_summarizes_current_employee_tickets_and_indexing(
    client: TestClient,
) -> None:
    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        headers={"X-Actor": "alice"},
        json={"name": "Support Playbooks", "department": "support"},
    ).json()
    uploaded = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
        headers={"X-Actor": "alice"},
        json={"source_name": "vpn.md", "content": "Use the enterprise account."},
    )
    assert uploaded.status_code == 201
    ticket_id = create_ticket_through_agent(client, "alice")
    create_ticket_through_agent(client, "bob")

    dashboard = client.get("/api/v1/dashboard", headers={"X-Actor": "alice"})

    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["actor"] == "alice"
    assert body["tickets"] == {
        "open_count": 1,
        "in_progress_count": 0,
        "resolved_count": 0,
        "closed_count": 0,
    }
    assert body["recent_tickets"][0]["id"] == ticket_id
    assert body["indexing"] == {
        "knowledge_base_count": 1,
        "document_count": 1,
        "ready_count": 0,
        "pending_count": 1,
        "failed_count": 0,
    }
    assert body["knowledge_bases"][0]["name"] == "Support Playbooks"


def test_dashboard_includes_current_employees_persisted_conversations(
    client: TestClient,
) -> None:
    turn = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "查看我的工单"},
    )
    assert turn.status_code == 201

    client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "bob"},
        json={"user_message": "查看我的工单"},
    )

    dashboard = client.get("/api/v1/dashboard", headers={"X-Actor": "alice"})

    assert dashboard.status_code == 200
    conversations = dashboard.json()["recent_conversations"]
    assert len(conversations) == 1
    assert conversations[0]["id"] == turn.json()["conversation_id"]
    assert conversations[0]["message_count"] == 2
