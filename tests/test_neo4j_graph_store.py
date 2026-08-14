"""Tests for the Neo4j GraphRAG storage adapter."""

from typing import Any

import pytest
from typing_extensions import Self

from knowledgeops.graphrag import GraphChunk, GraphEntity, Neo4jGraphStore


class FakeResult:
    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.records = records or []

    async def consume(self) -> None:
        return None

    async def data(self) -> list[dict[str, Any]]:
        return self.records


class FakeSession:
    def __init__(self, driver: "FakeDriver") -> None:
        self.driver = driver

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def run(
        self,
        query: str,
        **parameters: Any,
    ) -> FakeResult:
        self.driver.calls.append(
            {
                "query": query,
                "parameters": parameters,
            }
        )
        return FakeResult(self.driver.next_records)


class FakeDriver:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.next_records: list[dict[str, Any]] = []
        self.databases: list[str] = []
        self.closed = False

    def session(self, *, database: str) -> FakeSession:
        self.databases.append(database)
        return FakeSession(self)

    async def close(self) -> None:
        self.closed = True


def make_chunk() -> GraphChunk:
    return GraphChunk(
        chunk_id="chunk-a",
        document_id="document-a",
        knowledge_base_id="knowledge-base-a",
        source_name="vpn-runbook.md",
        chunk_index=0,
        text="VPN connection troubleshooting guide.",
    )


@pytest.mark.asyncio
async def test_neo4j_store_creates_entity_identity_constraint() -> None:
    driver = FakeDriver()
    store = Neo4jGraphStore(driver, database="knowledgeops")

    await store.ensure_schema()

    assert driver.databases == ["knowledgeops"]
    assert "CREATE CONSTRAINT graph_entity_identity" in driver.calls[0]["query"]


@pytest.mark.asyncio
async def test_neo4j_store_replaces_one_chunk_entity_mentions() -> None:
    driver = FakeDriver()
    store = Neo4jGraphStore(driver)

    await store.replace_chunk_entities(
        make_chunk(),
        [GraphEntity.from_name("VPN")],
    )

    request = driver.calls[0]
    assert "OPTIONAL MATCH" in request["query"]
    assert request["parameters"]["chunk"]["chunk_id"] == "chunk-a"
    assert request["parameters"]["entities"] == [
        {"name": "VPN", "key": "vpn"}
    ]


@pytest.mark.asyncio
async def test_neo4j_store_reads_chunks_within_one_knowledge_base() -> None:
    driver = FakeDriver()
    driver.next_records = [
        {
            "chunk_id": "chunk-a",
            "document_id": "document-a",
            "knowledge_base_id": "knowledge-base-a",
            "source_name": "vpn-runbook.md",
            "chunk_index": 0,
            "text": "VPN connection troubleshooting guide.",
        }
    ]
    store = Neo4jGraphStore(driver)

    results = await store.find_chunks(
        knowledge_base_id="knowledge-base-a",
        entity_keys=[" VPN "],
        limit=5,
    )

    assert [chunk.chunk_id for chunk in results] == ["chunk-a"]
    assert driver.calls[0]["parameters"]["entity_keys"] == ["vpn"]


@pytest.mark.asyncio
async def test_neo4j_store_closes_its_driver() -> None:
    driver = FakeDriver()
    store = Neo4jGraphStore(driver)

    await store.close()

    assert driver.closed is True