from knowledgeops.tasks.celery_indexing import (
    enqueue_document_index,
    index_document_task,
)


def test_celery_task_runs_async_indexing_flow(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_run_document_index(
        document_id: str,
        *,
        actor: str,
    ) -> dict[str, str | int]:
        captured["document_id"] = document_id
        captured["actor"] = actor
        return {
            "document_id": document_id,
            "status": "ready",
            "chunk_count": 2,
        }

    monkeypatch.setattr(
        "knowledgeops.tasks.celery_indexing.run_document_index",
        fake_run_document_index,
    )

    result = index_document_task.run(
        "document-001",
        actor="celery-test",
    )

    assert captured == {
        "document_id": "document-001",
        "actor": "celery-test",
    }
    assert result == {
        "document_id": "document-001",
        "status": "ready",
        "chunk_count": 2,
    }


def test_enqueue_document_index_returns_celery_task_id(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeAsyncResult:
        id = "celery-task-001"

    def fake_delay(document_id: str, *, actor: str) -> FakeAsyncResult:
        captured["document_id"] = document_id
        captured["actor"] = actor
        return FakeAsyncResult()

    monkeypatch.setattr(index_document_task, "delay", fake_delay)

    task_id = enqueue_document_index(
        "document-001",
        actor="api-user",
    )

    assert task_id == "celery-task-001"
    assert captured == {
        "document_id": "document-001",
        "actor": "api-user",
    }