"""Runtime task entry point for document embedding and Qdrant indexing."""

from qdrant_client import AsyncQdrantClient

from ..config import Settings
from ..db import Database
from ..models import Document
from ..rag import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    QdrantVectorStore,
    SemanticRetriever,
)
from ..services import DocumentIndexingService


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
    )
    return QdrantVectorStore(
        client,
        collection_name=settings.qdrant_collection,
        dimensions=settings.embedding_dimensions,
    )


def build_semantic_retriever(settings: Settings) -> SemanticRetriever:
    """Create the production semantic retriever from application settings."""
    embedding_provider = OpenAIEmbeddingProvider(
        model_name=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )
    vector_store = build_qdrant_vector_store(settings)

    return SemanticRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )


async def index_document(
    document_id: str,
    *,
    database: Database,
    settings: Settings,
    actor: str = "indexing-worker",
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> Document:
    """Run the complete document-to-vector indexing workflow.

    Production calls use the default OpenAI and Qdrant implementations.
    Tests may inject deterministic implementations to avoid real network calls.
    """
    # Injected dependencies belong to the caller; only close a client created here.
    owns_vector_store = vector_store is None
    active_vector_store = vector_store or build_qdrant_vector_store(settings)

    try:
        # AsyncOpenAI reads OPENAI_API_KEY from the environment in production.
        active_embedding_provider = embedding_provider or OpenAIEmbeddingProvider(
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

        # A task creates its own database session instead of reusing an HTTP request.
        async for session in database.session():
            service = DocumentIndexingService(
                session,
                embedding_provider=active_embedding_provider,
                vector_store=active_vector_store,
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