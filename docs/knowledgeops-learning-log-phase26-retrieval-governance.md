# Phase 26: Enterprise Retrieval Governance

## Why this change exists

The v0.4 evaluation revealed that multi-source evidence assembly was the
platform's weakest retrieval capability. The response was not to add rules for
the evaluation questions. Instead, this phase fixes two normal enterprise
problems:

1. A superseded policy can remain indexed and accidentally be cited.
2. Adjacent chunks from a long manual can consume all answer evidence slots.

## Design

`DocumentStatus` remains the technical indexing state (`uploaded`, `indexing`,
`ready`, `failed`). A new `DocumentLifecycle` represents business availability:

- `draft`: retained and indexable, but never returned by search.
- `active`: available to ordinary users and Agents.
- `archived`: excluded from ordinary searches; a caller must explicitly set
  `include_archived=true` to inspect historical material.

The lifecycle is persisted in PostgreSQL/SQLite and copied into Qdrant,
Elasticsearch, and Neo4j when a document is indexed. Changing the lifecycle of
a ready document updates metadata in those stores directly. It does not split
the source again or call the embedding model, so it avoids duplicate/stale
chunk IDs and unnecessary model cost.

## Retrieval behavior

Hybrid retrieval now recalls a configurable candidate pool (default: 20) even
when no reranker is present. After fusion and optional reranking, final results
are capped at two chunks per document by default. This makes a small evidence
list more likely to cover distinct source documents while retaining enough
adjacent context for a detailed runbook.

These limits are application configuration (`HYBRID_CANDIDATE_LIMIT` and
`HYBRID_MAX_CHUNKS_PER_DOCUMENT`), not query, title, or dataset-specific
heuristics.

## User-facing operation

The Knowledge Center now displays each document's indexing status and business
lifecycle, with an archive/publish action. The API is also available to other
management clients:

```http
PATCH /api/v1/documents/{document_id}/lifecycle
Content-Type: application/json

{"lifecycle": "archived"}
```

## Interview explanation

"I separated document indexing state from document business validity. A file
can be indexed successfully but still be a draft or retired policy, so normal
RAG retrieval must filter on governance metadata. I synchronized that metadata
across vector, keyword, and graph indexes without re-embedding. I also added a
per-document evidence cap after retrieval fusion, which improves source
coverage for real multi-document questions rather than tuning to a benchmark."

## Verification

The phase has focused unit and API tests for archive filtering, source
diversity, audit events, lifecycle synchronization contracts, and the document
management endpoint. No paid embedding or chat model call is needed for these
tests.
