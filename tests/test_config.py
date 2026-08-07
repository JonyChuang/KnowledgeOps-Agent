"""Tests for KnowledgeOps application configuration."""

from knowledgeops.config import Settings


def test_default_settings_require_alembic_migrations(monkeypatch):
    """A normal application start must not alter the database schema."""
    # Ignore the developer's real .env file so this test checks code defaults only.
    monkeypatch.delenv("AUTO_CREATE_SCHEMA", raising=False)
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    monkeypatch.delenv("EMBEDDING_DIMENSIONS", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)

    # _env_file=None prevents Pydantic from loading the project's real .env file.
    settings = Settings(_env_file=None)

    assert settings.auto_create_schema is False
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.qdrant_api_key is None
    assert settings.qdrant_collection == "knowledgeops_chunks"
    assert settings.embedding_dimensions == 512