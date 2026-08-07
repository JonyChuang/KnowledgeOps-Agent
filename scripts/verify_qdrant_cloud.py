"""Manually verify authenticated Qdrant Cloud read and write access."""

import asyncio

from qdrant_client import models

from knowledgeops.config import Settings
from knowledgeops.rag import VectorPoint
from knowledgeops.tasks.indexing import build_qdrant_vector_store

# A stable UUID lets this script clean up only the point it owns.
SMOKE_TEST_VECTOR_ID = "00000000-0000-4000-8000-000000000001"

# This payload makes the temporary point identifiable in Qdrant Cloud.
SMOKE_TEST_PAYLOAD = {
    "kind": "qdrant-cloud-smoke-test",
    "purpose": "temporary-connectivity-check",
}


async def verify_qdrant_cloud() -> None:
    """Create the configured collection, write one point, read it, and clean up."""
    # Settings() intentionally reads the local .env file for real cloud credentials.
    settings = Settings()

    if not settings.qdrant_url.startswith("https://"):
        raise RuntimeError("QDRANT_URL must be the HTTPS endpoint from Qdrant Cloud.")

    if settings.qdrant_api_key is None:
        raise RuntimeError("QDRANT_API_KEY is required for Qdrant Cloud.")

    if settings.embedding_dimensions < 1:
        raise RuntimeError("EMBEDDING_DIMENSIONS must be greater than zero.")

    vector_store = build_qdrant_vector_store(settings)

    # A non-zero vector is required by cosine similarity collections.
    smoke_test_vector = [0.0] * settings.embedding_dimensions
    smoke_test_vector[0] = 1.0
    point_written = False

    try:
        # This also creates knowledgeops_chunks with the configured dimension if absent.
        await vector_store.upsert_points(
            [
                VectorPoint(
                    vector_id=SMOKE_TEST_VECTOR_ID,
                    vector=smoke_test_vector,
                    payload=SMOKE_TEST_PAYLOAD,
                )
            ]
        )
        point_written = True

        payload = await vector_store.get_payload(SMOKE_TEST_VECTOR_ID)

        if payload != SMOKE_TEST_PAYLOAD:
            raise RuntimeError("Qdrant returned an unexpected smoke-test payload.")

        print("Qdrant Cloud connectivity verified.")
        print(f"Collection: {settings.qdrant_collection}")
        print(f"Dimensions: {settings.embedding_dimensions}")
    finally:
        # Remove only the point created by this script; keep the real collection.
        try:
            if point_written:
                await vector_store.client.delete(
                    collection_name=vector_store.collection_name,
                    points_selector=models.PointIdsList(
                        points=[SMOKE_TEST_VECTOR_ID]
                    ),
                    wait=True,
                )
                print("Temporary smoke-test point removed.")
        finally:
            # Always release the authenticated HTTP client.
            await vector_store.close()


if __name__ == "__main__":
    asyncio.run(verify_qdrant_cloud())