"""Integration coverage for the service-desk ticket queue."""

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings


@pytest.fixture
def client(tmp_path):
    database_path = (tmp_path / "service-desk.db").as_posix()
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


def create_ticket(client: TestClient, requester: str, title: str) -> str:
    response = client.post(
        "/api/v1/tickets",
        headers={"X-Actor": requester},
        json={"title": title, "description": "企业 VPN 客户端无法通过身份验证。"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_service_desk_processes_a_ticket_with_auditable_handoff(client: TestClient) -> None:
    ticket_id = create_ticket(client, "alice", "无法连接企业 VPN")
    first_line = service_desk_headers("first-line")
    network_team = service_desk_headers("network-team")

    denied = client.get("/api/v1/service-desk/tickets")
    assert denied.status_code == 403

    unassigned = client.get(
        "/api/v1/service-desk/tickets?scope=unassigned",
        headers=first_line,
    )
    assert unassigned.status_code == 200
    assert [item["id"] for item in unassigned.json()["items"]] == [ticket_id]

    accepted = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/accept",
        headers=first_line,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "in_progress"
    assert accepted.json()["assignee"] == "first-line"
    assert accepted.json()["activities"][-1]["event_type"] == "ticket.accepted"

    not_assignee = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/request-information",
        headers=network_team,
        json={"reason": "请补充 VPN 配置截图。"},
    )
    assert not_assignee.status_code == 409

    transferred = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/assign",
        headers=first_line,
        json={"assignee": "network-team"},
    )
    assert transferred.status_code == 200
    assert transferred.json()["assignee"] == "network-team"
    assert transferred.json()["activities"][-1]["event_type"] == "ticket.assigned"

    needs_information = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/request-information",
        headers=network_team,
        json={"reason": "请补充客户端错误截图。"},
    )
    assert needs_information.status_code == 200
    assert needs_information.json()["status"] == "awaiting_requester"

    requester_reply = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers={"X-Actor": "alice"},
        json={"content": "已补充客户端错误截图和发生时间。"},
    )
    assert requester_reply.status_code == 200
    assert requester_reply.json()["status"] == "in_progress"

    resolved = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/resolve",
        headers=network_team,
        json={"reason": "已重置 VPN 凭据并由员工确认连接恢复。"},
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "resolved"
    assert [item["event_type"] for item in body["activities"]] == [
        "ticket.created",
        "ticket.accepted",
        "ticket.assigned",
        "ticket.status_changed",
        "requester.comment_added",
        "ticket.status_changed",
        "ticket.status_changed",
    ]

    mine = client.get(
        "/api/v1/service-desk/tickets?scope=mine&status=resolved",
        headers=network_team,
    )
    assert [item["id"] for item in mine.json()["items"]] == [ticket_id]


def test_requester_cannot_use_service_desk_transition_endpoint(client: TestClient) -> None:
    ticket_id = create_ticket(client, "alice", "邮件客户端无法同步")

    removed_requester_transition = client.post(
        f"/api/v1/tickets/{ticket_id}/status",
        headers={"X-Actor": "alice"},
        json={"status": "in_progress", "reason": "不应由申请人受理。"},
    )
    assert removed_requester_transition.status_code == 404

    service_desk_detail = client.get(
        f"/api/v1/service-desk/tickets/{ticket_id}",
        headers=service_desk_headers("first-line"),
    )
    assert service_desk_detail.status_code == 200
    assert service_desk_detail.json()["requester"] == "alice"


def test_service_desk_cannot_transfer_a_ticket_waiting_for_requester(client: TestClient) -> None:
    ticket_id = create_ticket(client, "alice", "无法访问财务共享文件夹")
    operator = service_desk_headers("first-line")

    accepted = client.post(f"/api/v1/service-desk/tickets/{ticket_id}/accept", headers=operator)
    assert accepted.status_code == 200

    waiting = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/request-information",
        headers=operator,
        json={"reason": "请补充访问报错截图。"},
    )
    assert waiting.status_code == 200
    assert waiting.json()["status"] == "awaiting_requester"

    transfer = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/assign",
        headers=operator,
        json={"assignee": "network-team"},
    )
    assert transfer.status_code == 409
