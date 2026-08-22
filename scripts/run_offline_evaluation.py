"""Run the configured KnowledgeOps gold set and write an evidence report."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from pathlib import Path

from knowledgeops.config import get_settings
from knowledgeops.evaluation import (
    EvaluationDataset,
    evaluate_answer_verifier,
    evaluate_archive_isolation,
    evaluate_function_calling_agent,
    evaluate_multi_hop_answers,
    evaluate_retriever,
    load_evaluation_dataset,
    write_evaluation_report,
)
from knowledgeops.evaluation.live import build_answer_verifier, build_retrieval_baseline
from knowledgeops.tasks.agent import (
    build_chat_answer_generator,
    build_function_calling_agent,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run KnowledgeOps offline retrieval and Function Calling evaluation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to a versioned KnowledgeOps evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--skip-answers",
        action="store_true",
        help="Skip multi-hop grounded-answer evaluation when the dataset includes it.",
    )
    parser.add_argument(
        "--run-verifier",
        action="store_true",
        help="Run the independently configured VERIFIER_* model against answer gold labels.",
    )
    parser.add_argument(
        "--knowledge-base-id",
        help="Replace every retrieval case's placeholder knowledge_base_id for this run.",
    )
    parser.add_argument(
        "--methods",
        default="vector,bm25,hybrid,hybrid_rerank,graph",
        help="Comma-separated retrieval baselines to run.",
    )
    parser.add_argument("--k", type=int, default=5, help="Retrieval cutoff k.")
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Skip the side-effect-free Function Calling selection evaluation.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation-results"),
        help="Directory for report.md and report.json.",
    )
    return parser.parse_args()


def with_runtime_knowledge_base_id(
    dataset: EvaluationDataset,
    knowledge_base_id: str | None,
) -> EvaluationDataset:
    if not knowledge_base_id:
        return dataset
    return replace(
        dataset,
        retrieval_cases=tuple(
            replace(case, knowledge_base_id=knowledge_base_id)
            for case in dataset.retrieval_cases
        ),
        historical_retrieval_cases=tuple(
            replace(case, knowledge_base_id=knowledge_base_id)
            for case in dataset.historical_retrieval_cases
        ),
        multi_hop_cases=tuple(
            replace(case, knowledge_base_id=knowledge_base_id)
            for case in dataset.multi_hop_cases
        ),
    )


async def run(args: argparse.Namespace) -> tuple[Path, Path]:
    dataset = with_runtime_knowledge_base_id(
        load_evaluation_dataset(args.dataset),
        args.knowledge_base_id,
    )
    all_knowledge_base_ids = [
        *(case.knowledge_base_id for case in dataset.retrieval_cases),
        *(case.knowledge_base_id for case in dataset.historical_retrieval_cases),
        *(case.knowledge_base_id for case in dataset.multi_hop_cases),
    ]
    if any("replace-with" in value for value in all_knowledge_base_ids):
        raise ValueError(
            "Pass --knowledge-base-id or replace the placeholder in the dataset before running retrieval evaluation."
        )
    if args.k < 1:
        raise ValueError("--k must be greater than zero.")

    identifiers = {
        *(case.identifier for case in dataset.retrieval_cases),
        *(case.identifier for case in dataset.historical_retrieval_cases),
    }
    if len(identifiers) > 1:
        raise ValueError("A single run currently requires one retrieval identifier kind.")
    identifier = next(iter(identifiers), "chunk_id")
    result_identifier = (
        (lambda result: result.source_name)
        if identifier == "source_name"
        else None
    )

    settings = get_settings()
    retrieval_metrics = {}
    historical_retrieval_metrics = {}
    archive_isolation_metrics = {}
    methods = [method.strip() for method in args.methods.split(",") if method.strip()]
    for method in methods:
        retriever = build_retrieval_baseline(method, settings)
        try:
            retrieval_metrics[method] = await evaluate_retriever(
                retriever,
                [case.as_evaluation_case() for case in dataset.retrieval_cases],
                k=args.k,
                result_identifier=result_identifier,
            )
            if dataset.historical_retrieval_cases:
                historical_retrieval_metrics[method] = await evaluate_retriever(
                    retriever,
                    [case.as_evaluation_case() for case in dataset.historical_retrieval_cases],
                    k=args.k,
                    result_identifier=result_identifier,
                    include_archived=True,
                )
                archive_isolation_metrics[method] = await evaluate_archive_isolation(
                    retriever,
                    [case.as_evaluation_case() for case in dataset.historical_retrieval_cases],
                    k=args.k,
                )
        finally:
            await retriever.close()

    function_metrics = None
    if not args.skip_agent:
        function_agent = build_function_calling_agent(settings)
        if function_agent is None:
            raise ValueError(
                "CHAT_MODEL, CHAT_BASE_URL, and CHAT_API_KEY are required for Function Calling evaluation."
            )
        function_metrics = await evaluate_function_calling_agent(
            function_agent,
            dataset.agent_cases,
        )

    multi_hop_metrics = None
    if dataset.multi_hop_cases and not args.skip_answers:
        if not (
            settings.chat_model
            and settings.chat_api_key is not None
            and settings.chat_base_url
        ):
            raise ValueError(
                "CHAT_MODEL, CHAT_BASE_URL, and CHAT_API_KEY are required for multi-hop answer evaluation."
            )
        answer_retriever = build_retrieval_baseline("hybrid_rerank", settings)
        try:
            multi_hop_metrics = await evaluate_multi_hop_answers(
                answer_retriever,
                build_chat_answer_generator(settings),
                dataset.multi_hop_cases,
                k=4,
            )
        finally:
            await answer_retriever.close()

    verifier_metrics = None
    if args.run_verifier:
        if multi_hop_metrics is None:
            raise ValueError("--run-verifier requires multi-hop answer evaluation.")
        verifier = build_answer_verifier(settings)
        if verifier is None:
            raise ValueError(
                "VERIFIER_MODEL, VERIFIER_BASE_URL, and VERIFIER_API_KEY are required for independent verification."
            )
        verifier_metrics = await evaluate_answer_verifier(
            verifier,
            dataset.multi_hop_cases,
            multi_hop_metrics.results,
        )

    return write_evaluation_report(
        args.output_dir,
        dataset,
        retrieval_metrics=retrieval_metrics,
        historical_retrieval_metrics=historical_retrieval_metrics,
        archive_isolation_metrics=archive_isolation_metrics,
        function_calling_metrics=function_metrics,
        multi_hop_metrics=multi_hop_metrics,
        verifier_metrics=verifier_metrics,
    )


if __name__ == "__main__":
    markdown_path, json_path = asyncio.run(run(parse_args()))
    print(f"Wrote {markdown_path}")
    print(f"Wrote {json_path}")
