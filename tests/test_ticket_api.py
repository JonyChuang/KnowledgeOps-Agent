"""Integration coverage for the employee ticket list endpoints."""

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings


@pytest.fixture
def client(tmp_path):
    database_path = (tmp_path / "tickets.db").as_posix()
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


def create_ticket(client: TestClient, actor: str, title: str) -> str:
    pending = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": actor},
        json={"user_message": f"请帮我创建一个{title}工单"},
    )
    assert pending.status_code == 201
    confirmed = client.post(
        f"/api/v1/agent/turns/{pending.json()['thread_id']}/confirmation",
        headers={"X-Actor": actor},
        json={"approved": True},
    )
    assert confirmed.status_code == 200
    return confirmed.json()["created_ticket_id"]


def test_ticket_list_filters_searches_and_isolates_current_employee(
    client: TestClient,
) -> None:
    vpn_ticket_id = create_ticket(client, "alice", "VPN 无法连接")
    create_ticket(client, "alice", "笔记本无法开机")
    create_ticket(client, "bob", "VPN 无法连接")

    searched = client.get(
        "/api/v1/tickets?query=VPN&limit=1",
        headers={"X-Actor": "alice"},
    )

    assert searched.status_code == 200
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["id"] == vpn_ticket_id
    assert searched.json()["items"][0]["requester"] == "alice"

    first_page = client.get(
        "/api/v1/tickets?limit=1&offset=0",
        headers={"X-Actor": "alice"},
    )
    second_page = client.get(
        "/api/v1/tickets?limit=1&offset=1",
        headers={"X-Actor": "alice"},
    )

    assert first_page.json()["total"] == 2
    assert first_page.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]

    forbidden = client.get(
        f"/api/v1/tickets/{vpn_ticket_id}",
        headers={"X-Actor": "bob"},
    )

    assert forbidden.status_code == 404


def test_ticket_comment_is_visible_in_detail_and_isolated_by_requester(
    client: TestClient,
) -> None:
    ticket_id = create_ticket(client, "alice", "VPN 无法连接")

    commented = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers={"X-Actor": "alice"},
        json={"content": "补充：错误从今天上午开始出现。"},
    )

    assert commented.status_code == 200
    body = commented.json()
    assert [item["event_type"] for item in body["activities"]] == [
        "ticket.created",
        "requester.comment_added",
    ]
    assert body["activities"][-1]["content"] == "补充：错误从今天上午开始出现。"
    assert body["sla_due_at"] is not None

    forbidden = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers={"X-Actor": "bob"},
        json={"content": "尝试越权补充。"},
    )

    assert forbidden.status_code == 404


def test_ticket_resolution_actions_require_resolved_status(
    client: TestClient,
) -> None:
    ticket_id = create_ticket(client, "alice", "账号无法登录")

    confirm = client.post(
        f"/api/v1/tickets/{ticket_id}/confirm-resolution",
        headers={"X-Actor": "alice"},
    )
    reopen = client.post(
        f"/api/v1/tickets/{ticket_id}/reopen",
        headers={"X-Actor": "alice"},
        json={"reason": "仍然无法登录"},
    )

    assert confirm.status_code == 409
    assert reopen.status_code == 409


def test_requester_can_confirm_a_service_desk_resolution(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tickets",
        headers={"X-Actor": "alice"},
        json={
            "title": "VPN 无法连接",
            "description": "Windows 客户端身份验证失败。",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    accepted = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/accept",
        headers={"X-Actor": "service-desk", "X-Role": "service_desk"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "in_progress"
    assert accepted.json()["assignee"] == "service-desk"

    resolved = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/resolve",
        headers={"X-Actor": "service-desk", "X-Role": "service_desk"},
        json={"reason": "已重置 VPN 凭据并验证恢复。"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    closed = client.post(
        f"/api/v1/tickets/{ticket_id}/confirm-resolution",
        headers={"X-Actor": "alice"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    listed = client.get(
        "/api/v1/tickets?status=closed",
        headers={"X-Actor": "alice"},
    )
    assert [item["id"] for item in listed.json()["items"]] == [ticket_id]



def test_employee_can_create_a_standardized_ticket(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tickets",
        headers={"X-Actor": "alice"},
        json={
            "title": "共享文件夹无法访问",
            "description": "访问权限被拒绝。",
            "priority": "high",
            "category": "data_access",
            "impact": "team",
        },
    )

    assert created.status_code == 201
    body = created.json()
    assert body["requester"] == "alice"
    assert body["category"] == "data_access"
    assert body["impact"] == "team"
    assert body["sla_due_at"] is not None
