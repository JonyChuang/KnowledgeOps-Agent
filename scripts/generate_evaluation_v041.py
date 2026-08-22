"""Generate the v0.4.1 archive-governance evaluation dataset."""

from __future__ import annotations

import json
from pathlib import Path

from generate_evaluation_v04 import (
    PLACEHOLDER_KNOWLEDGE_BASE_ID,
    TOPICS,
    agent_cases,
    multi_hop_cases,
    security_cases,
)

ROOT = Path(__file__).parents[1]
DATASET_PATH = ROOT / "docs" / "evaluation" / "knowledgeops-gold-v0.4.1.json"

CURRENT_VARIANTS = (
    ("policy", "Policy", "APPROVAL_SCOPE=service_owner", "POLICY_ACTION=record business justification"),
    ("procedure", "Procedure", "STANDARD_ACTION=follow approved runbook", "PROCEDURE_RECORD=record owner and completion time"),
    ("exception", "Exception", "EXCEPTION_TRIGGER=high impact incident", "EXCEPTION_ACTION=escalate to service desk"),
)
ARCHIVE_VARIANT = (
    "archive",
    "Archived",
    "ARCHIVED_STATUS=do not use",
    "ARCHIVED_ACTION=use the current policy instead",
)


def _case(
    *,
    case_id: str,
    query: str,
    source_name: str,
    category: str,
) -> dict[str, object]:
    return {
        "id": case_id,
        "query": query,
        "knowledge_base_id": PLACEHOLDER_KNOWLEDGE_BASE_ID,
        "identifier": "source_name",
        "relevant_ids": [source_name],
        "category": category,
    }


def current_retrieval_cases() -> list[dict[str, object]]:
    """Evaluate only documents eligible for ordinary employee retrieval."""
    cases: list[dict[str, object]] = []
    for topic in TOPICS:
        slug, title, _domain, _scenario, paraphrase, _action, _record, contrast, _deadline = topic
        for variant_slug, variant_title, control, requirement in CURRENT_VARIANTS:
            source_name = f"{slug}-{variant_slug}.md"
            questions = (
                ("direct", f"What is the active {variant_title} for {title}? {control}"),
                ("paraphrase", f"An employee says '{paraphrase}'. Which current {title} {variant_title} document applies?"),
                ("boundary", f"For current {title}, distinguish {variant_title} from this boundary: {contrast}"),
                ("version", f"Is the {title} document with {control} the active version?"),
                ("process", f"When handling current {title}, which document requires: {requirement}?"),
            )
            cases.extend(
                _case(
                    case_id=f"current-{slug}-{variant_slug}-{style}",
                    query=query,
                    source_name=source_name,
                    category=f"current_{style}",
                )
                for style, query in questions
            )
    return cases


def historical_retrieval_cases() -> list[dict[str, object]]:
    """Evaluate archive search only when the caller explicitly enables it."""
    variant_slug, _variant_title, control, requirement = ARCHIVE_VARIANT
    cases: list[dict[str, object]] = []
    for topic in TOPICS:
        slug, title, _domain, _scenario, paraphrase, _action, _record, contrast, _deadline = topic
        source_name = f"{slug}-{variant_slug}.md"
        questions = (
            ("direct", f"For a historical audit, find the archived {title} record. {control}"),
            ("paraphrase", f"Historical review only: an employee said '{paraphrase}'. Which archived {title} document records this?"),
            ("boundary", f"For historical {title}, distinguish the archived record from this boundary: {contrast}"),
            ("version", f"In archive mode, find the non-current {title} document with {control}."),
            ("process", f"For audit purposes, which archived {title} document requires: {requirement}?"),
        )
        cases.extend(
            _case(
                case_id=f"history-{slug}-{style}",
                query=query,
                source_name=source_name,
                category=f"historical_{style}",
            )
            for style, query in questions
        )
    return cases


def main() -> None:
    dataset = {
        "schema_version": "knowledgeops-evaluation/v1",
        "dataset_version": "v0.4.1",
        "name": "KnowledgeOps archive-governance gold set",
        "retrieval_cases": current_retrieval_cases(),
        "historical_retrieval_cases": historical_retrieval_cases(),
        "agent_cases": agent_cases(),
        "multi_hop_cases": multi_hop_cases(),
        "security_cases": security_cases(),
    }
    DATASET_PATH.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(dataset['retrieval_cases'])} current and "
        f"{len(dataset['historical_retrieval_cases'])} historical retrieval cases to {DATASET_PATH}"
    )


if __name__ == "__main__":
    main()
