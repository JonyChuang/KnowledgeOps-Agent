import pytest

from knowledgeops.rag import FakeKeywordStore, KeywordPoint, KeywordSearchResult


def result(
    chunk_id: str,
    knowledge_base_id: str,
    text: str,
) -> KeywordSearchResult:
    return KeywordSearchResult(
        chunk_id=chunk_id,
        score=0.0,
        payload={
            "knowledge_base_id": knowledge_base_id,
            "text": text,
        },
    )


@pytest.mark.asyncio
async def test_fake_keyword_store_matches_and_orders_terms():
    store = FakeKeywordStore(
        [
            result("chunk-b", "support", "restart service"),
            result("chunk-a", "support", "restart service environment"),
            result("chunk-c", "support", "database backup"),
        ]
    )

    results = await store.search(
        "restart service",
        knowledge_base_id="support",
    )

    assert [item.chunk_id for item in results] == ["chunk-a", "chunk-b"]
    assert results[0].score == pytest.approx(2.0)
    assert results[1].score == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_fake_keyword_store_isolates_knowledge_bases():
    store = FakeKeywordStore(
        [
            result("support-chunk", "support", "restart service"),
            result("finance-chunk", "finance", "restart service"),
        ]
    )

    results = await store.search(
        "restart",
        knowledge_base_id="support",
    )

    assert [item.chunk_id for item in results] == ["support-chunk"]


@pytest.mark.asyncio
async def test_fake_keyword_store_validates_query_and_limit():
    store = FakeKeywordStore()

    with pytest.raises(ValueError, match="Query cannot be empty"):
        await store.search(" ", knowledge_base_id="support")

    with pytest.raises(ValueError, match="greater than zero"):
        await store.search("restart", knowledge_base_id="support", limit=0)


@pytest.mark.asyncio
async def test_fake_keyword_store_upserts_chunks():
    store = FakeKeywordStore()

    await store.upsert_points(
        [
            KeywordPoint(
                chunk_id="chunk-1",
                payload={
                    "knowledge_base_id": "support",
                    "text": "Restart the API service.",
                },
            )
        ]
    )

    results = await store.search(
        "restart",
        knowledge_base_id="support",
    )

    assert [result.chunk_id for result in results] == ["chunk-1"]
    await store.close()