"""Elasticsearch adapter for BM25 keyword retrieval."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from elasticsearch import AsyncElasticsearch

from .keyword_store import KeywordPoint, KeywordSearchResult

_INDEX_MAPPINGS: dict[str, Any] = {
    "properties": {
        "knowledge_base_id": {"type": "keyword"},
        "document_id": {"type": "keyword"},
        "source_name": {"type": "keyword"},
        "source_type": {"type": "keyword"},
        "chunk_index": {"type": "integer"},
        "start_char": {"type": "integer"},
        "end_char": {"type": "integer"},
        "text": {"type": "text"},
    }
}


class ElasticsearchKeywordStore:
    """Store chunks and retrieve BM25 matches from Elasticsearch."""

    def __init__(
        self,
        client: "AsyncElasticsearch",
        *,
        index_name: str,
    ) -> None:
        if not index_name.strip():
            raise ValueError("Elasticsearch index name cannot be empty.")

        self.client = client
        self.index_name = index_name

    async def ensure_index(self) -> None:
        """Create the searchable Chunk index when it does not exist."""
        exists = await self.client.indices.exists(index=self.index_name)
        if exists:
            return

        await self.client.indices.create(
            index=self.index_name,
            mappings=_INDEX_MAPPINGS,
        )

    async def upsert_points(self, points: list[KeywordPoint]) -> None:
        """Insert or replace searchable Chunk documents."""
        if not points:
            return

        await self.ensure_index()

        for point in points:
            await self.client.index(
                index=self.index_name,
                id=point.chunk_id,
                document=dict(point.payload),
                refresh="wait_for",
            )

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[KeywordSearchResult]:
        """Return BM25-ranked Chunk matches from one knowledge base."""
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Query cannot be empty.")

        if not knowledge_base_id.strip():
            raise ValueError("Knowledge base ID cannot be empty.")

        if limit < 1:
            raise ValueError("Search limit must be greater than zero.")

        response = await self.client.search(
            index=self.index_name,
            query={
                "bool": {
                    "must": [
                        {
                            "match": {
                                "text": clean_query,
                            }
                        }
                    ],
                    "filter": [
                        {
                            "term": {
                                "knowledge_base_id": knowledge_base_id,
                            }
                        }
                    ],
                }
            },
            size=limit,
        )

        response_body = getattr(response, "body", response)
        hits = response_body.get("hits", {}).get("hits", [])

        return [
            KeywordSearchResult(
                chunk_id=str(hit["_id"]),
                score=float(hit.get("_score") or 0.0),
                payload=dict(hit.get("_source") or {}),
            )
            for hit in hits
        ]

    async def close(self) -> None:
        """Release the Elasticsearch client connection."""
        await self.client.close()