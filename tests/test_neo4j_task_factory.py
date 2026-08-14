"""Tests for the production Neo4j graph-store factory."""

from knowledgeops.config import Settings
from knowledgeops.graphrag import Neo4jGraphStore
from knowledgeops.tasks.indexing import build_neo4j_graph_store


def test_build_neo4j_graph_store_reads_settings() -> None:
    captured: dict[str, object] = {}
    driver = object()

    def fake_driver_factory(
        uri: str,
        *,
        auth: tuple[str, str],
    ) -> object:
        captured["uri"] = uri
        captured["auth"] = auth
        return driver

    settings = Settings(
        neo4j_uri="bolt://neo4j.example:7687",
        neo4j_username="graph-user",
        neo4j_password="unit-test-password",
        neo4j_database="knowledgeops_graph",
    )

    graph_store = build_neo4j_graph_store(
        settings,
        driver_factory=fake_driver_factory,
    )

    assert isinstance(graph_store, Neo4jGraphStore)
    assert captured == {
        "uri": "bolt://neo4j.example:7687",
        "auth": ("graph-user", "unit-test-password"),
    }
    assert graph_store._database == "knowledgeops_graph"