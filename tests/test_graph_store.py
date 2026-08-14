"""Tests for the GraphRAG in-memory graph adapter."""

import pytest

from knowledgeops.graphrag import GraphChunk, GraphEntity, InMemoryGraphStore


def make_chunk(
    chunk_id: str,
    *,
    knowledge_base_id: str = "knowledge-base-a",
    text: str = "VPN connection troubleshooting guide.",
) -> GraphChunk:
    return GraphChunk(
        chunk_id=chunk_id,
        document_id=f"document-for-{chunk_id}",
        knowledge_base_id=knowledge_base_id,
        source_name="vpn-runbook.md",
        chunk_index=0,
        text=text,
    )


def test_graph_entity_normalizes_the_display_name_into_a_stable_key() -> None:
    entity = GraphEntity.from_name(" VPN ")

    assert entity.name == "VPN"
    assert entity.key == "vpn"


@pytest.mark.asyncio
async def test_graph_store_keeps_entity_search_inside_one_knowledge_base() -> None:
    store = InMemoryGraphStore()
    vpn = GraphEntity.from_name("VPN")

    await store.replace_chunk_entities(
        make_chunk("chunk-a", knowledge_base_id="knowledge-base-a"),
        [vpn],
    )
    await store.replace_chunk_entities(
        make_chunk("chunk-b", knowledge_base_id="knowledge-base-b"),
        [vpn],
    )

    results = await store.find_chunks(
        knowledge_base_id="knowledge-base-a",
        entity_keys=[" vpn "],
        limit=10,
    )

    assert [chunk.chunk_id for chunk in results] == ["chunk-a"]


@pytest.mark.asyncio
async def test_graph_store_replaces_old_entity_mentions_when_a_chunk_is_reindexed() -> None:
    store = InMemoryGraphStore()
    chunk = make_chunk("chunk-a")

    await store.replace_chunk_entities(
        chunk,
        [GraphEntity.from_name("VPN")],
    )
    await store.replace_chunk_entities(
        chunk,
        [GraphEntity.from_name("network")],
    )

    vpn_results = await store.find_chunks(
        knowledge_base_id="knowledge-base-a",
        entity_keys=["vpn"],
        limit=10,
    )
    network_results = await store.find_chunks(
        knowledge_base_id="knowledge-base-a",
        entity_keys=["network"],
        limit=10,
    )

    assert vpn_results == []
    assert [result.chunk_id for result in network_results] == ["chunk-a"]