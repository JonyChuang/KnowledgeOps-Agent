"""Neo4j-backed implementation of the GraphRAG storage boundary."""

from collections.abc import Sequence
from typing import Any

from .models import GraphChunk, GraphEntity, normalize_entity_key


class Neo4jGraphStore:
    """Persist entity-to-chunk relationships in a Neo4j graph."""

    def __init__(
        self,
        driver: Any,
        *,
        database: str = "neo4j",
    ) -> None:
        self._driver = driver
        self._database = database

    async def ensure_schema(self) -> None:
        """Create the graph constraints required for stable node identity."""
        entity_constraint = """
        CREATE CONSTRAINT graph_entity_identity IF NOT EXISTS
        FOR (entity:GraphEntity)
        REQUIRE (entity.knowledge_base_id, entity.key) IS UNIQUE
        """
        chunk_constraint = """
        CREATE CONSTRAINT graph_chunk_identity IF NOT EXISTS
        FOR (chunk:GraphChunk)
        REQUIRE chunk.chunk_id IS UNIQUE
        """

        async with self._driver.session(database=self._database) as session:
            for query in (entity_constraint, chunk_constraint):
                result = await session.run(query)
                await result.consume()

    async def replace_chunk_entities(
        self,
        chunk: GraphChunk,
        entities: Sequence[GraphEntity],
    ) -> None:
        """Replace a chunk's old entity mentions with its current mentions."""
        query = """
        MERGE (chunk:GraphChunk {chunk_id: $chunk.chunk_id})
        SET chunk.document_id = $chunk.document_id,
            chunk.knowledge_base_id = $chunk.knowledge_base_id,
            chunk.source_name = $chunk.source_name,
            chunk.chunk_index = $chunk.chunk_index,
            chunk.text = $chunk.text,
            chunk.document_lifecycle = $chunk.lifecycle
        WITH chunk
        OPTIONAL MATCH (chunk)-[mention:MENTIONS]->(:GraphEntity)
        DELETE mention
        WITH chunk
        UNWIND $entities AS entity
        MERGE (
            graph_entity:GraphEntity {
                knowledge_base_id: $chunk.knowledge_base_id,
                key: entity.key
            }
        )
        SET graph_entity.name = entity.name
        MERGE (chunk)-[:MENTIONS]->(graph_entity)
        """

        chunk_payload = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "knowledge_base_id": chunk.knowledge_base_id,
            "source_name": chunk.source_name,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "lifecycle": chunk.lifecycle,
        }
        entity_payloads = [
            {
                "name": entity.name,
                "key": entity.key,
            }
            for entity in entities
        ]

        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                chunk=chunk_payload,
                entities=entity_payloads,
            )
            await result.consume()

    async def find_chunks(
        self,
        *,
        knowledge_base_id: str,
        entity_keys: Sequence[str],
        limit: int,
        include_archived: bool = False,
    ) -> list[GraphChunk]:
        """Find chunks connected to entities within the requested knowledge base."""
        if not knowledge_base_id.strip():
            raise ValueError("Knowledge base ID cannot be empty.")
        if limit <= 0:
            raise ValueError("Search limit must be greater than zero.")

        normalized_keys = [
            normalize_entity_key(entity_key)
            for entity_key in entity_keys
            if entity_key.strip()
        ]
        if not normalized_keys:
            return []

        query = """
        MATCH (chunk:GraphChunk)-[:MENTIONS]->(entity:GraphEntity)
        WHERE chunk.knowledge_base_id = $knowledge_base_id
          AND entity.knowledge_base_id = $knowledge_base_id
          AND entity.key IN $entity_keys
          AND coalesce(chunk.document_lifecycle, 'active') <> 'draft'
          AND ($include_archived OR coalesce(chunk.document_lifecycle, 'active') <> 'archived')
        RETURN DISTINCT
            chunk.chunk_id AS chunk_id,
            chunk.document_id AS document_id,
            chunk.knowledge_base_id AS knowledge_base_id,
            chunk.source_name AS source_name,
            chunk.chunk_index AS chunk_index,
            chunk.text AS text,
            coalesce(chunk.document_lifecycle, 'active') AS lifecycle
        ORDER BY document_id, chunk_index, chunk_id
        LIMIT $limit
        """

        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                knowledge_base_id=knowledge_base_id,
                entity_keys=normalized_keys,
                limit=limit,
                include_archived=include_archived,
            )
            records = await result.data()

        return [
            GraphChunk(
                chunk_id=record["chunk_id"],
                document_id=record["document_id"],
                knowledge_base_id=record["knowledge_base_id"],
                source_name=record["source_name"],
                chunk_index=record["chunk_index"],
                text=record["text"],
                lifecycle=record["lifecycle"],
            )
            for record in records
        ]

    async def update_document_lifecycle(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
        lifecycle: str,
    ) -> None:
        query = """
        MATCH (chunk:GraphChunk {
            knowledge_base_id: $knowledge_base_id,
            document_id: $document_id
        })
        SET chunk.document_lifecycle = $lifecycle
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                lifecycle=lifecycle,
            )
            await result.consume()

    async def close(self) -> None:
        """Close the Neo4j driver owned by this store."""
        await self._driver.close()
