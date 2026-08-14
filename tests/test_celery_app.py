from knowledgeops.config import Settings
from knowledgeops.tasks.celery_app import create_celery_app


def test_celery_app_reads_settings() -> None:
    settings = Settings(
        _env_file=None,
        celery_broker_url="redis://broker.example:6379/0",
        celery_result_backend="redis://result.example:6379/1",
    )

    celery_app = create_celery_app(settings)

    assert celery_app.conf.broker_url == (
        "redis://broker.example:6379/0"
    )
    assert celery_app.conf.result_backend == (
        "redis://result.example:6379/1"
    )
    assert celery_app.conf.task_default_queue == "knowledgeops"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"

    assert celery_app.conf.imports == (
        "knowledgeops.tasks.celery_indexing",
    )