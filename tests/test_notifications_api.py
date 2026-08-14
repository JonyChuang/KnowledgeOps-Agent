"""Integration coverage for recipient-scoped operational notifications."""

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings


@pytest.fixture
def client(tmp_path):
    database_path = (tmp_path / "notifications.db").as_posix()
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


def service_desk_headers(operator: str) -> dict[str, str]:
    return {"X-Actor": operator, "X-Role": "service_desk"}


def create_ticket(client: TestClient, requester: str = "alice") -> str:
    response = client.post(
        "/api/v1/tickets",
        headers={"X-Actor": requester},
        json={
            "title": "企业 VPN 无法连接",
            "description": "客户端身份验证失败，影响远程办公。",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def notifications_for(client: TestClient, actor: str, **params: str) -> dict:
    response = client.get(
        "/api/v1/notifications",
        headers={"X-Actor": actor},
        params=params,
    )
    assert response.status_code == 200
    return response.json()


def test_ticket_collaboration_creates_recipient_scoped_notifications(
    client: TestClient,
) -> None:
    ticket_id = create_ticket(client)

    accepted = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/accept",
        headers=service_desk_headers("first-line"),
    )
    assert accepted.status_code == 200

    alice_after_accept = notifications_for(client, "alice")
    assert alice_after_accept["unread_count"] == 1
    assert alice_after_accept["items"][0]["title"] == "工单已受理"
    assert alice_after_accept["items"][0]["entity_id"] == ticket_id
    assert alice_after_accept["items"][0]["target_view"] == "tickets"
    assert notifications_for(client, "bob")["total"] == 0
    assert notifications_for(client, "first-line")["total"] == 0

    transferred = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/assign",
        headers=service_desk_headers("first-line"),
        json={"assignee": "network-team"},
    )
    assert transferred.status_code == 200

    team_notifications = notifications_for(client, "network-team")
    assert team_notifications["total"] == 1
    assert team_notifications["items"][0]["title"] == "有工单转派给你"
    assert team_notifications["items"][0]["target_view"] == "service-desk"
    assert notifications_for(client, "alice")["total"] == 2


def test_notifications_can_be_read_individually_or_in_bulk(client: TestClient) -> None:
    ticket_id = create_ticket(client)
    accepted = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/accept",
        headers=service_desk_headers("service-desk"),
    )
    assert accepted.status_code == 200

    requested = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/request-information",
        headers=service_desk_headers("service-desk"),
        json={"reason": "请补充客户端版本和错误截图。"},
    )
    assert requested.status_code == 200

    page = notifications_for(client, "alice")
    assert page["total"] == 2
    assert page["unread_count"] == 2

    first_id = page["items"][0]["id"]
    read = client.post(
        f"/api/v1/notifications/{first_id}/read",
        headers={"X-Actor": "alice"},
    )
    assert read.status_code == 200
    assert read.json()["is_read"] is True

    unread_only = notifications_for(client, "alice", unread_only="true")
    assert unread_only["total"] == 1
    assert unread_only["unread_count"] == 1

    bulk = client.post(
        "/api/v1/notifications/read-all",
        headers={"X-Actor": "alice"},
    )
    assert bulk.status_code == 200
    assert bulk.json() == {"updated_count": 1}
    assert notifications_for(client, "alice")["unread_count"] == 0


def test_notifications_cannot_be_read_by_another_employee(client: TestClient) -> None:
    ticket_id = create_ticket(client)
    accepted = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/accept",
        headers=service_desk_headers("service-desk"),
    )
    assert accepted.status_code == 200

    notification_id = notifications_for(client, "alice")["items"][0]["id"]
    denied = client.post(
        f"/api/v1/notifications/{notification_id}/read",
        headers={"X-Actor": "bob"},
    )
    assert denied.status_code == 404
    assert notifications_for(client, "alice")["unread_count"] == 1
