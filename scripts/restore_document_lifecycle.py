"""Restore a known set of current documents without re-indexing their content.

This is a local maintenance command. It calls the same service used by the API,
so vector, keyword, graph metadata, database state, and audit events stay aligned.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from knowledgeops.config import Settings
from knowledgeops.db import create_database
from knowledgeops.models import DocumentLifecycle, DocumentStatus
from knowledgeops.services import KnowledgeService
from knowledgeops.tasks import build_elasticsearch_keyword_store, build_qdrant_vector_store
from knowledgeops.tasks.indexing import build_neo4j_graph_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore current knowledge-base documents to active lifecycle.")
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--expected-total", required=True, type=int)
    parser.add_argument("--expected-current", required=True, type=int)
    parser.add_argument("--expected-archived", required=True, type=int)
    parser.add_argument("--archive-suffix", default="-archive.md")
    parser.add_argument("--actor", default="local-maintenance")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _validate_preflight(documents: list[object], args: argparse.Namespace) -> tuple[list[object], list[object]]:
    current = [document for document in documents if not document.source_name.endswith(args.archive_suffix)]
    archived = [document for document in documents if document.source_name.endswith(args.archive_suffix)]
    to_publish = [document for document in current if document.lifecycle is DocumentLifecycle.ARCHIVED]
    unexpected_current = [document for document in current if document.lifecycle is not DocumentLifecycle.ARCHIVED]
    unexpected_archived = [document for document in archived if document.lifecycle is not DocumentLifecycle.ARCHIVED]

    counts = {
        "total": len(documents),
        "current": len(current),
        "archived": len(archived),
        "to_publish": len(to_publish),
        "unexpected_current": len(unexpected_current),
        "unexpected_archived": len(unexpected_archived),
    }
    expected = {
        "total": args.expected_total,
        "current": args.expected_current,
        "archived": args.expected_archived,
        "to_publish": args.expected_current,
        "unexpected_current": 0,
        "unexpected_archived": 0,
    }
    if counts != expected:
        raise RuntimeError(f"Preflight failed: actual={counts}, expected={expected}")
    return to_publish, archived


async def run(args: argparse.Namespace) -> dict[str, int | bool]:
    settings = Settings()
    database = create_database(settings)
    vector_store = None
    keyword_store = None
    graph_store = None

    try:
        async with database.session_factory() as session:
            service = KnowledgeService(session)
            documents = await service.list_documents(args.knowledge_base_id)
            to_publish, _ = _validate_preflight(documents, args)

            if args.dry_run:
                return {"dry_run": True, "planned_updates": len(to_publish)}

            if any(document.status is DocumentStatus.READY for document in to_publish):
                vector_store = build_qdrant_vector_store(settings)
                keyword_store = build_elasticsearch_keyword_store(settings)
                if settings.graph_indexing_enabled:
                    graph_store = build_neo4j_graph_store(settings)

            for document in to_publish:
                await service.update_document_lifecycle(
                    document.id,
                    DocumentLifecycle.ACTIVE,
                    actor=args.actor,
                    vector_store=vector_store,
                    keyword_store=keyword_store,
                    graph_store=graph_store,
                )

            verified = await service.list_documents(args.knowledge_base_id)
            active = [document for document in verified if document.lifecycle is DocumentLifecycle.ACTIVE]
            archived = [document for document in verified if document.lifecycle is DocumentLifecycle.ARCHIVED]
            invalid_active = [document for document in active if document.source_name.endswith(args.archive_suffix)]
            invalid_archived = [document for document in archived if not document.source_name.endswith(args.archive_suffix)]
            if (
                len(active) != args.expected_current
                or len(archived) != args.expected_archived
                or invalid_active
                or invalid_archived
            ):
                raise RuntimeError(
                    "Post-update verification failed: "
                    f"active={len(active)}, archived={len(archived)}, "
                    f"invalid_active={len(invalid_active)}, invalid_archived={len(invalid_archived)}"
                )
            return {"dry_run": False, "updated": len(to_publish), "active": len(active), "archived": len(archived)}
    finally:
        if vector_store is not None:
            await vector_store.close()
        if keyword_store is not None:
            await keyword_store.close()
        if graph_store is not None:
            await graph_store.close()
        await database.dispose()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(parse_args())), ensure_ascii=True))
