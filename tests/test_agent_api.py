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
    )

    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_agent_turn_requires_owner_confirmation_before_creating_ticket(
    client: TestClient,
) -> None:
    initial = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "请帮我创建一个 VPN 无法连接的工单"},
    )

    assert initial.status_code == 201
    initial_body = initial.json()
    assert initial_body["status"] == "confirmation_required"
    assert initial_body["pending_action"]["action_type"] == "ticket.create"
    assert initial_body["created_ticket_id"] is None

    thread_id = initial_body["thread_id"]
    rejected_actor = client.post(
        f"/api/v1/agent/turns/{thread_id}/confirmation",
        headers={"X-Actor": "bob"},
        json={"approved": True},
    )

    assert rejected_actor.status_code == 404

    confirmed = client.post(
        f"/api/v1/agent/turns/{thread_id}/confirmation",
        headers={"X-Actor": "alice"},
        json={"approved": True},
    )

    assert confirmed.status_code == 200
    confirmed_body = confirmed.json()
    assert confirmed_body["status"] == "completed"
    assert confirmed_body["created_ticket_id"] is not None
    assert confirmed_body["ticket_ids"] == [
        confirmed_body["created_ticket_id"]
    ]

    repeated_confirmation = client.post(
        f"/api/v1/agent/turns/{thread_id}/confirmation",
        headers={"X-Actor": "alice"},
        json={"approved": True},
    )

    assert repeated_confirmation.status_code == 409
    assert repeated_confirmation.json()["detail"] == (
        "Agent conversation has no pending confirmation."
    )

    queried = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "查看我的工单"},
    )

    assert queried.status_code == 201
    assert queried.json()["ticket_ids"] == [
        confirmed_body["created_ticket_id"]
    ]


def test_agent_turn_can_cancel_ticket_creation(client: TestClient) -> None:
    initial = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "请帮我创建一个 VPN 无法连接的工单"},
    )

    thread_id = initial.json()["thread_id"]
    cancelled = client.post(
        f"/api/v1/agent/turns/{thread_id}/confirmation",
        headers={"X-Actor": "alice"},
        json={"approved": False},
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["created_ticket_id"] is None
    assert cancelled.json()["ticket_ids"] == []

    queried = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "查看我的工单"},
    )

    assert queried.status_code == 201
    assert queried.json()["ticket_ids"] == []


def test_agent_turn_explains_when_free_chat_model_is_not_configured(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "你好"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert "尚未配置 Chat 模型" in body["answer"]
    assert body["citations"] == []


def test_agent_conversation_persists_and_is_isolated_by_actor(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "查看我的工单"},
    )

    assert created.status_code == 201
    conversation_id = created.json()["conversation_id"]
    assert conversation_id is not None

    listed = client.get(
        "/api/v1/agent/conversations",
        headers={"X-Actor": "alice"},
    )

    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == conversation_id
    assert listed.json()["items"][0]["message_count"] == 2

    restored = client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers={"X-Actor": "alice"},
    )

    assert restored.status_code == 200
    assert [message["role"] for message in restored.json()["messages"]] == [
        "user",
        "agent",
    ]
    assert restored.json()["messages"][0]["content"] == "查看我的工单"

    forbidden = client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers={"X-Actor": "bob"},
    )
    assert forbidden.status_code == 404


def test_agent_can_continue_a_persisted_conversation(client: TestClient) -> None:
    first = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={"user_message": "查看我的工单"},
    )
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={
            "user_message": "查看我的工单",
            "conversation_id": conversation_id,
        },
    )

    assert second.status_code == 201
    assert second.json()["conversation_id"] == conversation_id
    restored = client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers={"X-Actor": "alice"},
    )
    assert len(restored.json()["messages"]) == 4
