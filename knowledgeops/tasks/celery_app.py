"""Celery application configuration for KnowledgeOps background work."""

from celery import Celery

from ..config import Settings, get_settings


def create_celery_app(settings: Settings) -> Celery:
    """Create a Celery app without connecting to Redis at import time."""
    app = Celery(
        "knowledgeops",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_default_queue="knowledgeops",
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        timezone="UTC",
        enable_utc=True,
        imports=("knowledgeops.tasks.celery_indexing",),
    )
    return app


celery_app = create_celery_app(get_settings())