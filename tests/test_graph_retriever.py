"""Tests for GraphRAG entity-based chunk retrieval."""

import pytest

from knowledgeops.graphrag import (
    GraphChunk,
    GraphEntity,
    GraphRetriever,
    InMemoryGraphStore,
    RuleBasedEntityExtractor,
)


def make_chunk(
    chunk_id: str,
    *,
    knowledge_base_id: str = "knowledge-base-a",
    text: str = "VPN troubleshooting requires network checks.",
) -> GraphChunk:
    return GraphChunk(
        chunk_id=chunk_id,
        document_id=f"document-{chunk_id}",
        knowledge_base_id=knowledge_base_id,
        source_name=f"{chunk_id}.md",
        chunk_index=0,
        text=text,
    )


@pytest.mark.asyncio
async def test_graph_retriever_finds_chunks_by_entities_in_the_question() -> None:
    graph_store = InMemoryGraphStore()
    extractor = RuleBasedEntityExtractor(
        entity_names=["VPN", "network"],
    )
    await graph_store.replace_chunk_entities(
        make_chunk("vpn-runbook"),
        [GraphEntity.from_name("VPN"), GraphEntity.from_name("network")],
    )
    retriever = GraphRetriever(
        graph_store=graph_store,
        entity_extractor=extractor,
    )

    chunks = await retriever.retrieve(
        "How should I troubleshoot a VPN connection?",
        knowledge_base_id="knowledge-base-a",
        limit=5,
    )

    assert [chunk.chunk_id for chunk in chunks] == ["vpn-runbook"]


@pytest.mark.asyncio
async def test_graph_retriever_returns_no_chunks_when_no_entity_is_recognized() -> None:
    graph_store = InMemoryGraphStore()
    retriever = GraphRetriever(
        graph_store=graph_store,
        entity_extractor=RuleBasedEntityExtractor(entity_names=["VPN"]),
    )

    chunks = await retriever.retrieve(
        "How do I reset my password?",
        knowledge_base_id="knowledge-base-a",
        limit=5,
    )

    assert chunks == []


@pytest.mark.asyncio
async def test_graph_retriever_rejects_invalid_search_input() -> None:
    retriever = GraphRetriever(
        graph_store=InMemoryGraphStore(),
        entity_extractor=RuleBasedEntityExtractor(entity_names=["VPN"]),
    )

    with pytest.raises(ValueError, match="Query cannot be empty"):
        await retriever.retrieve(
            " ",
            knowledge_base_id="knowledge-base-a",
            limit=5,
        )

    with pytest.raises(ValueError, match="Search limit must be greater than zero"):
        await retriever.retrieve(
            "VPN",
            knowledge_base_id="knowledge-base-a",
            limit=0,
        )