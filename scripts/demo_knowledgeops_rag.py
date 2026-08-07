"""Run a real KnowledgeOps indexing and semantic-search demonstration."""

import asyncio
import tempfile
from pathlib import Path

from knowledgeops.config import Settings
from knowledgeops.db import Database
from knowledgeops.rag import OpenAIEmbeddingProvider, SemanticRetriever
from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate
from knowledgeops.services import KnowledgeService
from knowledgeops.tasks import (
    build_qdrant_vector_store,
    index_document,
)

DEMO_DOCUMENT = """# Fictional API Operations Handbook

The Aurora API service runs in three environments: development, staging, and production.

When environment variables change, restart the API process so the new configuration is loaded.
After restarting, call the health endpoint and confirm that the response status is ok.

For a failed deployment, first inspect the application logs, then roll back to the previous version.
Only the release owner may approve a production rollback.
"""


async def run_demo() -> None:
    """Index a fictional document and retrieve a cited chunk from Qdrant Cloud."""
    # Use a temporary database so the demo does not modify knowledgeops.db.
    with tempfile.TemporaryDirectory(prefix="knowledgeops-demo-") as temp_dir:
        database_path = Path(temp_dir) / "demo.db"
        settings = Settings(
            database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
            auto_create_schema=True,
        )
        database = Database(settings.database_url)
        vector_store = build_qdrant_vector_store(settings)
        embedding_provider = OpenAIEmbeddingProvider(
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

        try:
            await database.create_schema()

            # Persist a fictional knowledge base and document locally.
            async for session in database.session():
                knowledge_service = KnowledgeService(session)
                knowledge_base = await knowledge_service.create_knowledge_base(
                    KnowledgeBaseCreate(
                        name="KnowledgeOps Demo Handbook",
                        description="Fictional public demonstration data.",
                        department="platform",
                    ),
                    actor="demo",
                )
                document = await knowledge_service.upload_text_document(
                    knowledge_base.id,
                    TextDocumentCreate(
                        source_name="aurora-api-handbook.md",
                        source_type="markdown",
                        content=DEMO_DOCUMENT,
                    ),
                    actor="demo",
                )

            # Run the real OpenAI Embedding -> Qdrant Cloud indexing path.
            indexed_document = await index_document(
                document.id,
                database=database,
                settings=settings,
                actor="demo",
                embedding_provider=embedding_provider,
                vector_store=vector_store,
            )

            print(f"Indexed status: {indexed_document.status.value}")
            print(f"Chunk count: {indexed_document.chunk_count}")

            # Reuse the same real providers for semantic retrieval.
            retriever = SemanticRetriever(
                embedding_provider=embedding_provider,
                vector_store=vector_store,
            )
            results = await retriever.retrieve(
                "What should I do after changing environment variables?",
                knowledge_base_id=knowledge_base.id,
                limit=3,
            )

            print("Search results:")
            for result in results:
                print(
                    f"- score={result.score:.4f} "
                    f"source={result.source_name} "
                    f"chunk={result.chunk_index}"
                )
                print(f"  {result.text[:180]}")

        finally:
            # The Qdrant collection remains for inspection; the demo point data
            # can be removed from the Cloud dashboard after the demonstration.
            await vector_store.close()
            await database.dispose()


if __name__ == "__main__":
    asyncio.run(run_demo())