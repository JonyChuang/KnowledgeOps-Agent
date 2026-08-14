"""Integration coverage for global search, personal shortcuts, and Agent feedback."""

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings


@pytest.fixture
def client(tmp_path):
    database_path = (tmp_path / "engagement.db").as_posix()
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


def workspace_payload(
    *,
    entity_type: str = "knowledge_base",
    entity_id: str = "kb-001",
    title: str = "VPN 服务手册",
    target_view: str = "knowledge",
) -> dict:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "title": title,
        "subtitle": "远程办公与 VPN 排障流程。",
        "target_view": target_view,
        "target_id": entity_id,
        "metadata_json": {"source": "test"},
    }


def create_ticket(client: TestClient, actor: str, title: str) -> str:
    response = client.post(
        "/api/v1/tickets",
        headers={"X-Actor": actor},
        json={"title": title, "description": "企业 VPN 客户端身份验证失败。"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_favorites_and_recent_visits_are_employee_scoped_and_idempotent(
    client: TestClient,
) -> None:
    payload = workspace_payload()
    first = client.post("/api/v1/favorites", headers={"X-Actor": "alice"}, json=payload)
    second = client.post("/api/v1/favorites", headers={"X-Actor": "alice"}, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/v1/favorites", headers={"X-Actor": "alice"}).json()["items"]) == 1
    assert client.get("/api/v1/favorites", headers={"X-Actor": "bob"}).json()["items"] == []

    visited = client.post("/api/v1/recent-visits", headers={"X-Actor": "alice"}, json=payload)
    revisited = client.post("/api/v1/recent-visits", headers={"X-Actor": "alice"}, json=payload)
    assert visited.status_code == 201
    assert revisited.status_code == 201
    assert visited.json()["id"] == revisited.json()["id"]
    assert len(client.get("/api/v1/recent-visits", headers={"X-Actor": "alice"}).json()["items"]) == 1

    removed = client.delete(
        "/api/v1/favorites/knowledge_base/kb-001",
        headers={"X-Actor": "alice"},
    )
    assert removed.status_code == 204
    assert client.get("/api/v1/favorites", headers={"X-Actor": "alice"}).json()["items"] == []


def test_global_search_aggregates_documents_tickets_conversations_and_graph_entities(
    client: TestClient,
) -> None:
    knowledge_base = client.post(
        "/api/v1/knowledge-bases",
        headers={"X-Actor": "alice"},
        json={"name": "VPN 运维手册", "department": "it"},
    ).json()
    uploaded = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
        headers={"X-Actor": "alice"},
        json={"source_name": "vpn.md", "content": "VPN 客户端连接失败时检查账号权限。"},
    )
    assert uploaded.status_code == 201
    ticket_id = create_ticket(client, "alice", "VPN 无法连接")
    bob_ticket_id = create_ticket(client, "bob", "VPN 无法连接")
    conversation = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "查看我的 VPN 工单"},
    )
    assert conversation.status_code == 201

    search = client.get(
        "/api/v1/search",
        headers={"X-Actor": "alice"},
        params={"query": "VPN"},
    )
    assert search.status_code == 200
    items = search.json()["items"]
    types = {item["entity_type"] for item in items}
    assert {"document", "ticket", "conversation", "graph"}.issubset(types)
    ticket_result_ids = {item["entity_id"] for item in items if item["entity_type"] == "ticket"}
    assert ticket_result_ids == {ticket_id}
    assert bob_ticket_id not in ticket_result_ids


def test_agent_feedback_requires_owner_of_persisted_agent_message(client: TestClient) -> None:
    turn = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "你好"},
    )
    assert turn.status_code == 201
    conversation_id = turn.json()["conversation_id"]
    detail = client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers={"X-Actor": "alice"},
    )
    agent_message_id = next(
        item["id"] for item in detail.json()["messages"] if item["role"] == "agent"
    )

    saved = client.post(
        f"/api/v1/agent-messages/{agent_message_id}/feedback",
        headers={"X-Actor": "alice"},
        json={"feedback_type": "incorrect_answer", "comment": "回答缺少具体步骤。"},
    )
    assert saved.status_code == 200
    assert saved.json()["feedback_type"] == "incorrect_answer"

    updated = client.post(
        f"/api/v1/agent-messages/{agent_message_id}/feedback",
        headers={"X-Actor": "alice"},
        json={"feedback_type": "helpful"},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == saved.json()["id"]
    assert updated.json()["feedback_type"] == "helpful"

    denied = client.post(
        f"/api/v1/agent-messages/{agent_message_id}/feedback",
        headers={"X-Actor": "bob"},
        json={"feedback_type": "unhelpful"},
    )
    assert denied.status_code == 404
