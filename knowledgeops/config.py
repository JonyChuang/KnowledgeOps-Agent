from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "KnowledgeOps Agent"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"
    # SQLite makes local development and automated tests self-contained.
    # Docker Compose will override DATABASE_URL with a PostgreSQL connection.
    database_url: str = "sqlite+aiosqlite:///./knowledgeops.db"
    # Local development creates tables automatically.
    # Production containers will run Alembic migrations instead.
    auto_create_schema: bool = False

    # Qdrant stores vectors while PostgreSQL or SQLite stores business records.
    qdrant_url: str = "http://localhost:6333"

    # SecretStr prevents the API Key from appearing in Settings logs or repr output.
    qdrant_api_key: SecretStr | None = None

    qdrant_collection: str = "knowledgeops_chunks"
    embedding_dimensions: int = 512
    # Keep the embedding model configurable across local and deployed environments.
    embedding_model: str = "text-embedding-3-small"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()