import pytest

from knowledgeops.agents.tools import (
    DatabaseKnowledgeBaseScopeTool,
    HybridKnowledgeSearchTool,
    LazyKnowledgeSearchTool,
)
from knowledgeops.rag.hybrid_retriever import HybridRetrievedChunk
from knowledgeops.repositories import ReadyDocumentChunk


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.closed = False

    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
    ) -> list[HybridRetrievedChunk]:
        self.calls.append((query, knowledge_base_id, limit))

        return [
            HybridRetrievedChunk(
                chunk_id="chunk-001",
                score=0.91,
                sources=("vector", "keyword"),
                knowledge_base_id=knowledge_base_id,
                document_id="document-001",
                source_name="vpn-guide.md",
                source_type="markdown",
                chunk_index=0,
                start_char=0,
                end_char=18,
                text="VPN 连接需要使用企业账号。",
                rerank_score=0.88,
            )
        ]

    async def close(self) -> None:
        self.closed = True


class FakeDocumentChunkRepository:
    def __init__(self, chunks: list[ReadyDocumentChunk]) -> None:
        self.chunks = chunks
        self.calls: list[tuple[str, int]] = []

    async def list_ready_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 3,
    ) -> list[ReadyDocumentChunk]:
        self.calls.append((knowledge_base_id, limit))
        return self.chunks


@pytest.mark.asyncio
async def test_tool_maps_hybrid_results_to_agent_citations() -> None:
    retriever = FakeRetriever()
    tool = HybridKnowledgeSearchTool(retriever)

    citations = await tool.search(
        "VPN 怎么连接？",
        knowledge_base_id="kb-001",
        limit=3,
    )

    assert retriever.calls == [("VPN 怎么连接？", "kb-001", 3)]
    assert len(citations) == 1
    assert citations[0].chunk_id == "chunk-001"
    assert citations[0].text == "VPN 连接需要使用企业账号。"
    assert citations[0].sources == ["vector", "keyword"]
    assert citations[0].score == 0.91
    assert citations[0].rerank_score == 0.88


@pytest.mark.asyncio
async def test_tool_closes_underlying_retriever() -> None:
    retriever = FakeRetriever()
    tool = HybridKnowledgeSearchTool(retriever)

    await tool.close()

    assert retriever.closed is True


@pytest.mark.asyncio
async def test_lazy_tool_creates_retriever_only_when_searching() -> None:
    retriever = FakeRetriever()
    factory_calls = 0

    def build_retriever() -> FakeRetriever:
        nonlocal factory_calls
        factory_calls += 1
        return retriever

    tool = LazyKnowledgeSearchTool(build_retriever)

    await tool.close()
    assert factory_calls == 0
    assert retriever.closed is False

    await tool.search(
        "VPN 怎么连接？",
        knowledge_base_id="kb-001",
        limit=3,
    )
    await tool.search(
        "VPN 怎么连接？",
        knowledge_base_id="kb-001",
        limit=3,
    )
    await tool.close()

    assert factory_calls == 1
    assert retriever.closed is True


@pytest.mark.asyncio
async def test_scope_tool_maps_ready_document_chunks_to_citations() -> None:
    repository = FakeDocumentChunkRepository(
        [
            ReadyDocumentChunk(
                id="chunk-coverage-001",
                document_id="document-coverage-001",
                source_name="vpn-runbook.md",
                source_type="markdown",
                chunk_index=0,
                start_char=0,
                end_char=24,
                text="VPN troubleshooting steps.",
            )
        ]
    )
    tool = DatabaseKnowledgeBaseScopeTool(repository)  # type: ignore[arg-type]

    citations = await tool.list_ready_citations(
        knowledge_base_id="kb-coverage-001",
    )

    assert repository.calls == [("kb-coverage-001", 3)]
    assert citations[0].source_name == "vpn-runbook.md"
    assert citations[0].score == 0.0
    assert citations[0].sources == ["knowledge_base_scope"]
