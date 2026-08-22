"""Runtime task entry point for document embedding and Qdrant indexing."""

from collections.abc import Callable

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from ..config import Settings
from ..db import Database
from ..graphrag import (
    EntityExtractor,
    GraphStore,
    Neo4jGraphStore,
    RuleBasedEntityExtractor,
)
from ..models import Document
from ..rag import (
    ElasticsearchKeywordStore,
    EmbeddingProvider,
    HybridRetriever,
    KeywordStore,
    OpenAIEmbeddingProvider,
    QdrantVectorStore,
    SemanticRetriever,
    TokenOverlapReranker,
)
from ..services import DocumentIndexingService


def build_embedding_provider(settings: Settings) -> OpenAIEmbeddingProvider:
    if settings.embedding_api_key is None:
        raise ValueError("EMBEDDING_API_KEY is required.")

    client = AsyncOpenAI(
        api_key=settings.embedding_api_key.get_secret_value(),
        base_url=settings.embedding_base_url,
    )
    return OpenAIEmbeddingProvider(
        model_name=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        client=client,
    )


def build_qdrant_vector_store(settings: Settings) -> QdrantVectorStore:
    """Create the production Qdrant adapter from application settings."""
    # Extract the secret only when creating the authenticated client.
    api_key = (
        settings.qdrant_api_key.get_secret_value()
        if settings.qdrant_api_key is not None
        else None
    )

    # The URL and API Key come from Settings instead of being hard-coded.
    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=api_key,
        # Some Windows httpx/zstd combinations fail while decoding a tiny
        # local Qdrant response. The collection API is small, so disabling
        # content compression is a reliable and negligible-cost workaround.
        headers={"Accept-Encoding": "identity"},
        trust_env=settings.qdrant_trust_env,
    )
    return QdrantVectorStore(
        client,
        collection_name=settings.qdrant_collection,
        dimensions=settings.embedding_dimensions,
    )


def build_elasticsearch_keyword_store(
    settings: Settings,
    *,
    client_factory: Callable[..., object] | None = None,
) -> ElasticsearchKeywordStore:
    """Create the production Elasticsearch adapter from application settings."""
    if client_factory is None:
        # Only production code needs the real Elasticsearch HTTP client.
        from elasticsearch import AsyncElasticsearch

        client_factory = AsyncElasticsearch

    api_key = (
        settings.elasticsearch_api_key.get_secret_value()
        if settings.elasticsearch_api_key is not None
        else None
    )
    client = client_factory(
        hosts=[settings.elasticsearch_url],
        api_key=api_key,
    )
    return ElasticsearchKeywordStore(
        client,
        index_name=settings.elasticsearch_index,
    )


def build_neo4j_graph_store(
    settings: Settings,
    *,
    driver_factory: Callable[..., object] | None = None,
) -> Neo4jGraphStore:
    """Create the production Neo4j adapter from application settings."""
    if settings.neo4j_password is None:
        raise ValueError("NEO4J_PASSWORD is required when graph indexing is enabled.")

    if driver_factory is None:
        from neo4j import AsyncGraphDatabase

        driver_factory = AsyncGraphDatabase.driver

    driver = driver_factory(
        settings.neo4j_uri,
        auth=(
            settings.neo4j_username,
            settings.neo4j_password.get_secret_value(),
        ),
    )
    return Neo4jGraphStore(
        driver,
        database=settings.neo4j_database,
    )


def build_semantic_retriever(settings: Settings) -> SemanticRetriever:
    """Create the production semantic retriever from application settings."""
    embedding_provider = build_embedding_provider(settings)
    vector_store = build_qdrant_vector_store(settings)

    return SemanticRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )


def build_hybrid_retriever(settings: Settings) -> HybridRetriever:
    """Create the production hybrid retriever from application settings."""
    return HybridRetriever(
        semantic_retriever=build_semantic_retriever(settings),
        keyword_store=build_elasticsearch_keyword_store(settings),
        reranker=TokenOverlapReranker(),
        candidate_limit=settings.hybrid_candidate_limit,
        max_chunks_per_document=settings.hybrid_max_chunks_per_document,
    )

async def index_document(
    document_id: str,
    *,
    database: Database,
    settings: Settings,
    actor: str = "indexing-worker",
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: QdrantVectorStore | None = None,
    keyword_store: KeywordStore | None = None,
    graph_store: GraphStore | None = None,
    entity_extractor: EntityExtractor | None = None,
) -> Document:
    """Run the complete document-to-vector indexing workflow.

    Production calls use the default OpenAI and Qdrant implementations.
    Tests may inject deterministic implementations to avoid real network calls.
    """
    # Injected dependencies belong to the caller; only close a client created here.
    # Injected dependencies belong to the caller; only close stores built here.
    owns_graph_store = False
    active_graph_store = graph_store

    if active_graph_store is None and settings.graph_indexing_enabled:
        active_graph_store = build_neo4j_graph_store(settings)
        owns_graph_store = True

    if active_graph_store is None:
        if entity_extractor is not None:
            raise ValueError("Entity extractor requires a graph store.")
        active_entity_extractor = None
    else:
        active_entity_extractor = (
            entity_extractor or RuleBasedEntityExtractor()
        )
    owns_vector_store = vector_store is None
    owns_keyword_store = keyword_store is None
    active_vector_store = vector_store or build_qdrant_vector_store(settings)
    active_keyword_store = (
        keyword_store
        or build_elasticsearch_keyword_store(settings)
    )

    try:
        if active_graph_store is not None:
            await active_graph_store.ensure_schema()
        # AsyncOpenAI reads OPENAI_API_KEY from the environment in production.
        active_embedding_provider = embedding_provider or build_embedding_provider(settings)
        # A task creates its own database session instead of reusing an HTTP request.
        async for session in database.session():
            service = DocumentIndexingService(
                session,
                embedding_provider=active_embedding_provider,
                vector_store=active_vector_store,
                keyword_store=active_keyword_store,
                graph_store=active_graph_store,
                entity_extractor=active_entity_extractor,
            )
            return await service.index_document(
                document_id,
                actor=actor,
            )



        # Database.session() should always yield once; this guards against misuse.
        raise RuntimeError("Database session context did not yield a session.")
    finally:
        # Release the HTTP client only when this task constructed it.
        if owns_vector_store:
            await active_vector_store.close()

        if owns_keyword_store:
            await active_keyword_store.close()

        if owns_graph_store and active_graph_store is not None:
            await active_graph_store.close()
