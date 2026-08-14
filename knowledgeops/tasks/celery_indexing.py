"""Celery entry points for document indexing."""

import asyncio

from ..config import get_settings
from ..db import create_database
from .celery_app import celery_app
from .indexing import index_document


async def run_document_index(
    document_id: str,
    *,
    actor: str,
) -> dict[str, str | int]:
    """Create worker-owned runtime resources and run async indexing."""
    settings = get_settings()
    database = create_database(settings)

    try:
        document = await index_document(
            document_id,
            database=database,
            settings=settings,
            actor=actor,
        )
        return {
            "document_id": document.id,
            "status": document.status.value,
            "chunk_count": document.chunk_count,
        }
    finally:
        await database.dispose()


@celery_app.task(name="knowledgeops.index_document")
def index_document_task(
    document_id: str,
    *,
    actor: str = "celery-worker",
) -> dict[str, str | int]:
    """Bridge Celery's synchronous worker API to async business code."""
    return asyncio.run(
        run_document_index(
            document_id,
            actor=actor,
        )
    )


def enqueue_document_index(
    document_id: str,
    *,
    actor: str,
) -> str:
    """Publish one small, JSON-serializable indexing message to Redis."""
    result = index_document_task.delay(document_id, actor=actor)
    return str(result.id)