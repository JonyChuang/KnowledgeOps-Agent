"""End-to-end coverage for browser session authentication and role authorization."""

import pytest
from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings


@pytest.fixture
def client(tmp_path):
    database_path = (tmp_path / "auth.db").as_posix()
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        auto_create_schema=True,
        auth_jwt_secret="test-secret-that-is-long-enough-for-authentication",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def register(client: TestClient, username: str, password: str = "correct-password") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "display_name": username.title(), "password": password},
    )
    assert response.status_code == 201
    return response.json()


def test_first_registered_user_is_administrator_and_session_is_cookie_based(client: TestClient) -> None:
    body = register(client, "alice")

    assert body["user"]["username"] == "alice"
    assert body["user"]["role"] == "admin"
    assert "knowledgeops_access_token" in client.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "alice"

    # Headers cannot make an authenticated browser session impersonate another user.
    dashboard = client.get("/api/v1/dashboard", headers={"X-Actor": "mallory"})
    assert dashboard.status_code == 200
    assert dashboard.json()["actor"] == "alice"


def test_logout_revokes_current_session(client: TestClient) -> None:
    register(client, "alice")
    logged_out = client.post("/api/v1/auth/logout")
    assert logged_out.status_code == 204

    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/dashboard").status_code == 401


def test_service_desk_access_requires_server_side_role(client: TestClient) -> None:
    register(client, "admin")
    client.post("/api/v1/auth/logout")
    employee = register(client, "employee")
    employee_id = employee["user"]["id"]

    forbidden = client.get("/api/v1/service-desk/tickets")
    assert forbidden.status_code == 403

    client.post("/api/v1/auth/logout")
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "correct-password"}).status_code == 200
    promoted = client.patch(
        f"/api/v1/auth/users/{employee_id}/role",
        json={"role": "service_desk"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "service_desk"

    client.post("/api/v1/auth/logout")
    assert client.post("/api/v1/auth/login", json={"username": "employee", "password": "correct-password"}).status_code == 200
    assert client.get("/api/v1/service-desk/tickets").status_code == 200


def test_wrong_password_and_unauthenticated_requests_are_rejected(client: TestClient) -> None:
    register(client, "alice")
    client.post("/api/v1/auth/logout")

    failed_login = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong-password"})
    assert failed_login.status_code == 401
    assert client.get("/api/v1/agent/conversations", headers={"X-Actor": "alice"}).status_code == 401


def test_authenticated_user_can_update_profile_and_password(client: TestClient) -> None:
    register(client, "alice")

    profile = client.patch("/api/v1/auth/me", json={"display_name": "Alice Chen"})
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Alice Chen"

    rejected = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "not-the-password", "new_password": "new-correct-password"},
    )
    assert rejected.status_code == 400

    changed = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "correct-password", "new_password": "new-correct-password"},
    )
    assert changed.status_code == 204

    client.post("/api/v1/auth/logout")
    assert client.post("/api/v1/auth/login", json={"username": "alice", "password": "correct-password"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "alice", "password": "new-correct-password"}).status_code == 200
