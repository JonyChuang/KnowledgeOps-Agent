"""Tests for KnowledgeOps application configuration."""

from knowledgeops.config import Settings


def test_default_settings_require_alembic_migrations(tmp_path, monkeypatch):
    """A normal application start must not alter the database schema."""
    # Isolate the test from a project .env file and process environment variables.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AUTO_CREATE_SCHEMA", raising=False)

    settings = Settings()

    assert settings.auto_create_schema is False