"""Release-gate integration checks represented by the v0.4 security corpus."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings
from knowledgeops.services.web_import import WebImportError, fetch_web_page


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'security-v04.db').as_posix()}",
        auto_create_schema=True,
        auth_test_mode=True,
        chat_model=None,
        chat_api_key=None,
        chat_base_url=None,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _create_ticket(client: TestClient, actor: str = "alice") -> str:
    response = client.post(
        "/api/v1/tickets",
        headers={"X-Actor": actor},
        json={"title": "VPN unavailable", "description": "Evaluation ticket"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_agent_confirmation_creates_exactly_one_ticket(client: TestClient) -> None:
    initial = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={
            "user_message": (
                "VPN 在 Windows 11 客户端报错 619，重启后仍失败，"
                "已持续三十分钟，只影响我本人，请创建工单。"
            )
        },
    )
    assert initial.status_code == 201
    body = initial.json()
    assert body["status"] == "confirmation_required"
    assert client.get("/api/v1/tickets", headers={"X-Actor": "alice"}).json()["total"] == 0

    confirmed = client.post(
        f"/api/v1/agent/turns/{body['thread_id']}/confirmation",
        headers={"X-Actor": "alice"},
        json={"approved": True},
    )
    assert confirmed.status_code == 200
    assert client.get("/api/v1/tickets", headers={"X-Actor": "alice"}).json()["total"] == 1

    repeated = client.post(
        f"/api/v1/agent/turns/{body['thread_id']}/confirmation",
        headers={"X-Actor": "alice"},
        json={"approved": True},
    )
    assert repeated.status_code == 409
    assert client.get("/api/v1/tickets", headers={"X-Actor": "alice"}).json()["total"] == 1


def test_cancelled_agent_draft_creates_no_ticket(client: TestClient) -> None:
    initial = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={
            "user_message": (
                "VPN 在 Windows 11 客户端报错 619，重启后仍失败，"
                "已持续三十分钟，只影响我本人，请创建工单。"
            )
        },
    ).json()

    cancelled = client.post(
        f"/api/v1/agent/turns/{initial['thread_id']}/confirmation",
        headers={"X-Actor": "alice"},
        json={"approved": False},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["created_ticket_id"] is None
    assert client.get("/api/v1/tickets", headers={"X-Actor": "alice"}).json()["total"] == 0


def test_ticket_and_agent_confirmation_are_scoped_to_employee(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    assert client.get(
        f"/api/v1/tickets/{ticket_id}", headers={"X-Actor": "bob"}
    ).status_code == 404

    initial = client.post(
        "/api/v1/agent/turns",
        headers={"X-Actor": "alice"},
        json={
            "user_message": (
                "VPN 在 Windows 11 客户端报错 619，重启后仍失败，"
                "已持续三十分钟，只影响我本人，请创建工单。"
            )
        },
    ).json()
    assert client.post(
        f"/api/v1/agent/turns/{initial['thread_id']}/confirmation",
        headers={"X-Actor": "bob"},
        json={"approved": True},
    ).status_code == 404


def test_requester_cannot_claim_or_transition_service_desk_ticket(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    assert client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/accept",
        headers={"X-Actor": "alice"},
    ).status_code == 403


def test_service_desk_transition_keeps_audit_activity(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    accepted = client.post(
        f"/api/v1/service-desk/tickets/{ticket_id}/accept",
        headers={"X-Actor": "first-line", "X-Role": "service_desk"},
    )
    assert accepted.status_code == 200
    assert [activity["event_type"] for activity in accepted.json()["activities"]] == [
        "ticket.created",
        "ticket.accepted",
    ]


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/internal", "http://10.0.0.1/internal", "http://user:pass@example.com"],
)
def test_web_import_rejects_unsafe_destinations(url: str) -> None:
    with pytest.raises(WebImportError):
        asyncio.run(fetch_web_page(url, max_bytes=1024, timeout_seconds=1))


def test_unsupported_local_file_type_is_rejected(client: TestClient) -> None:
    knowledge_base = client.post(
        "/api/v1/knowledge-bases", json={"name": "Security imports"}
    ).json()
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents/upload",
        params={"source_name": "payload.exe"},
        content=b"not an importable document",
    )
    assert response.status_code == 422
