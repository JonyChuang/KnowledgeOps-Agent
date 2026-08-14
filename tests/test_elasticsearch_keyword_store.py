from typing import Any

import pytest

from knowledgeops.rag import ElasticsearchKeywordStore, KeywordPoint


class FakeIndices:
    def __init__(self, *, exists: bool) -> None:
        self.exists_value = exists
        self.exists_calls: list[str] = []
        self.create_calls: list[dict[str, Any]] = []

    async def exists(self, *, index: str) -> bool:
        self.exists_calls.append(index)
        return self.exists_value

    async def create(
        self,
        *,
        index: str,
        mappings: dict[str, Any],
    ) -> None:
        self.create_calls.append(
            {
                "index": index,
                "mappings": mappings,
            }
        )


class FakeElasticsearchClient:
    def __init__(
        self,
        *,
        index_exists: bool,
        search_response: dict[str, Any] | None = None,
    ) -> None:
        self.indices = FakeIndices(exists=index_exists)
        self.index_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []
        self.search_response = search_response or {"hits": {"hits": []}}
        self.closed = False

    async def index(
        self,
        *,
        index: str,
        id: str,
        document: dict[str, Any],
        refresh: str,
    ) -> None:
        self.index_calls.append(
            {
                "index": index,
                "id": id,
                "document": document,
                "refresh": refresh,
            }
        )

    async def search(self, **kwargs: Any) -> dict[str, Any]:
        self.search_calls.append(dict(kwargs))
        return self.search_response

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_elasticsearch_store_creates_mapping_and_upserts_chunks():
    """Chunks should use their stable IDs when stored in Elasticsearch."""
    client = FakeElasticsearchClient(index_exists=False)
    store = ElasticsearchKeywordStore(
        client,
        index_name="knowledgeops_chunks",
    )
    payload = {
        "knowledge_base_id": "support",
        "document_id": "document-1",
        "source_name": "support-guide.md",
        "source_type": "markdown",
        "chunk_index": 0,
        "start_char": 0,
        "end_char": 20,
        "text": "Restart the API service.",
    }

    await store.upsert_points(
        [
            KeywordPoint(
                chunk_id="chunk-1",
                payload=payload,
            )
        ]
    )

    assert client.indices.exists_calls == ["knowledgeops_chunks"]
    assert len(client.indices.create_calls) == 1

    mappings = client.indices.create_calls[0]["mappings"]["properties"]
    assert mappings["knowledge_base_id"] == {"type": "keyword"}
    assert mappings["text"] == {"type": "text"}

    assert client.index_calls == [
        {
            "index": "knowledgeops_chunks",
            "id": "chunk-1",
            "document": payload,
            "refresh": "wait_for",
        }
    ]


@pytest.mark.asyncio
async def test_elasticsearch_store_searches_with_bm25_and_knowledge_base_filter():
    """Search must combine BM25 text matching with server-side isolation."""
    payload = {
        "knowledge_base_id": "support",
        "document_id": "document-1",
        "source_name": "support-guide.md",
        "source_type": "markdown",
        "chunk_index": 0,
        "start_char": 0,
        "end_char": 24,
        "text": "Restart the API service.",
    }
    client = FakeElasticsearchClient(
        index_exists=True,
        search_response={
            "hits": {
                "hits": [
                    {
                        "_id": "chunk-1",
                        "_score": 4.25,
                        "_source": payload,
                    }
                ]
            }
        },
    )
    store = ElasticsearchKeywordStore(
        client,
        index_name="knowledgeops_chunks",
    )

    results = await store.search(
        "restart API",
        knowledge_base_id="support",
        limit=3,
    )

    assert [result.chunk_id for result in results] == ["chunk-1"]
    assert results[0].score == pytest.approx(4.25)
    assert results[0].payload == payload

    request = client.search_calls[0]
    assert request["index"] == "knowledgeops_chunks"
    assert request["size"] == 3
    assert request["query"]["bool"]["must"] == [
        {
            "match": {
                "text": "restart API",
            }
        }
    ]
    assert request["query"]["bool"]["filter"] == [
        {
            "term": {
                "knowledge_base_id": "support",
            }
        }
    ]

    await store.close()
    assert client.closed is True


@pytest.mark.asyncio
async def test_elasticsearch_store_validates_search_input_before_network_calls():
    """Invalid input must fail before Elasticsearch receives a request."""
    client = FakeElasticsearchClient(index_exists=True)
    store = ElasticsearchKeywordStore(
        client,
        index_name="knowledgeops_chunks",
    )

    with pytest.raises(ValueError, match="Query cannot be empty"):
        await store.search(" ", knowledge_base_id="support")

    with pytest.raises(ValueError, match="Knowledge base ID cannot be empty"):
        await store.search("restart", knowledge_base_id=" ")

    with pytest.raises(ValueError, match="Search limit must be greater than zero"):
        await store.search("restart", knowledge_base_id="support", limit=0)

    assert client.search_calls == []