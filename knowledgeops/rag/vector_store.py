"""Qdrant vector storage adapter."""

from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient, models


@dataclass(frozen=True)
class VectorPoint:
    """One vector and its source metadata."""

    vector_id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True)
class VectorSearchResult:
    """One Qdrant nearest-neighbor result and its source metadata."""

    vector_id: str
    score: float
    payload: dict[str, Any]


class QdrantVectorStore:
    """Create collections and persist vectors in Qdrant."""

    def __init__(
        self,
        client: AsyncQdrantClient,
        *,
        collection_name: str,
        dimensions: int,
    ):
        self.client = client
        self.collection_name = collection_name
        self.dimensions = dimensions

    async def ensure_collection(self) -> None:
        """Create the collection, verify dimensions, and prepare filter indexes."""
        exists = await self.client.collection_exists(self.collection_name)

        if not exists:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimensions,
                    distance=models.Distance.COSINE,
                ),
            )
        else:
            info = await self.client.get_collection(self.collection_name)
            configured_vectors = info.config.params.vectors

            if configured_vectors.size != self.dimensions:
                raise ValueError(
                    "Qdrant collection dimension does not match the embedding dimension."
                )

        # Qdrant Cloud requires an index when we filter search results by payload.
        # This project filters chunks by knowledge_base_id, so the index must exist
        # before semantic search can safely run in production.
        await self._ensure_payload_indexes()

    async def _ensure_payload_indexes(self) -> None:
        """Create payload indexes used by semantic-search filters."""
        await self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="knowledge_base_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )

    async def upsert_points(self, points: list[VectorPoint]) -> None:
        """Insert or replace vectors and their metadata."""
        for point in points:
            # Qdrant rejects vectors whose length differs from the collection size.
            if len(point.vector) != self.dimensions:
                raise ValueError("Vector dimension does not match the collection.")

        if not points:
            return

        await self.ensure_collection()

        qdrant_points = [
            models.PointStruct(
                id=point.vector_id,
                vector=point.vector,
                payload=point.payload,
            )
            for point in points
        ]

        await self.client.upsert(
            collection_name=self.collection_name,
            points=qdrant_points,
            wait=True,
        )

    async def get_payload(self, vector_id: str) -> dict[str, Any] | None:
        """Read one vector's metadata for citation lookup."""
        records = await self.client.retrieve(
            collection_name=self.collection_name,
            ids=[vector_id],
            with_payload=True,
            with_vectors=False,
        )

        if not records:
            return None

        return dict(records[0].payload or {})

    async def search(
        self,
        query_vector: list[float],
        *,
        limit: int = 5,
        knowledge_base_id: str | None = None,
    ) -> list[VectorSearchResult]:
        """Return nearest vectors, optionally limited to one knowledge base."""
        if len(query_vector) != self.dimensions:
            raise ValueError("Query vector dimension does not match the collection.")

        if limit < 1:
            raise ValueError("Search limit must be greater than zero.")

        # Searching an empty knowledge base should return an empty result list,
        # not fail because its collection has not yet been created.
        await self.ensure_collection()

        query_filter = None
        if knowledge_base_id is not None:
            # Payload filtering prevents one department from retrieving another
            # knowledge base's document chunks.
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="knowledge_base_id",
                        match=models.MatchValue(value=knowledge_base_id),
                    )
                ]
            )

        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return [
            VectorSearchResult(
                vector_id=str(point.id),
                score=point.score,
                payload=dict(point.payload or {}),
            )
            for point in response.points
        ]

    async def close(self) -> None:
        """Release the Qdrant client connection."""
        await self.client.close()

