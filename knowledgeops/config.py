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
    # Redis separates task messages from task-result records.
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    database_url: str = "sqlite+aiosqlite:///./knowledgeops.db"
    # Local development creates tables automatically.
    # Production containers will run Alembic migrations instead.
    auto_create_schema: bool = False

    # Qdrant stores vectors while PostgreSQL or SQLite stores business records.
    qdrant_url: str = "http://localhost:6333"

    # Local Qdrant should not inherit a terminal SOCKS/HTTP proxy. Enable this
    # explicitly only when a remote Qdrant deployment requires that proxy.
    qdrant_trust_env: bool = False

    # SecretStr prevents the API Key from appearing in Settings logs or repr output.
    qdrant_api_key: SecretStr | None = None

    qdrant_collection: str = "knowledgeops_chunks"

    # Elasticsearch stores searchable text for BM25 keyword retrieval.
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_api_key: SecretStr | None = None
    elasticsearch_index: str = "knowledgeops_chunks"

    # Recall a wider generic pool before selecting final, source-diverse evidence.
    hybrid_candidate_limit: int = 20
    hybrid_max_chunks_per_document: int = 2

    embedding_dimensions: int = 512
    # Keep the embedding model configurable across local and deployed environments.
    embedding_model: str = "text-embedding-3-small"

    # Chat 模型：理解用户意图、生成知识库回答。
    chat_model: str | None = None
    chat_temperature: float = 0

    # Chat 和 Embedding 可以使用不同服务商、地址和密钥。
    chat_base_url: str | None = None
    chat_api_key: SecretStr | None = None
    # Optional independent model for evaluation-only answer verification. It is
    # intentionally separate from CHAT_* so reports can disclose self-review.
    verifier_model: str | None = None
    verifier_base_url: str | None = None
    verifier_api_key: SecretStr | None = None
    embedding_base_url: str | None = None
    embedding_api_key: SecretStr | None = None

    # Neo4j stores explicit entity-to-chunk relationships for GraphRAG.
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: SecretStr | None = None
    neo4j_database: str = "neo4j"
    graph_indexing_enabled: bool = False

    # Import limits apply before source content enters the database or indexer.
    document_upload_max_bytes: int = 10_000_000
    web_import_max_bytes: int = 2_000_000
    web_import_timeout_seconds: float = 10.0

    # Browser sessions are signed and checked against a server-side session record.
    # Override this value through AUTH_JWT_SECRET before deploying outside local development.
    auth_jwt_secret: SecretStr = SecretStr("development-only-change-this-jwt-secret-before-production")
    auth_access_token_ttl_seconds: int = 28_800
    auth_cookie_secure: bool = False
    # Test suites explicitly opt in to header-based identities. It must remain false in every deployment.
    auth_test_mode: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def uses_development_auth_secret(self) -> bool:
        return self.auth_jwt_secret.get_secret_value() == "development-only-change-this-jwt-secret-before-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
