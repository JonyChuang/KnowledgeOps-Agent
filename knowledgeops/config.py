from functools import lru_cache

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()