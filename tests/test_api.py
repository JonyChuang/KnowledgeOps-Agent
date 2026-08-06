from fastapi.testclient import TestClient

from knowledgeops.api import create_app
from knowledgeops.config import Settings


def test_health_check(tmp_path):
    """Health checks should start and stop with an isolated SQLite database."""
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database_path}",
        auto_create_schema=True,
    )

    # TestClient context management executes the FastAPI lifespan function.
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "knowledgeops-api",
    }