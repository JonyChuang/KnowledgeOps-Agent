"""Measure bounded concurrent retrieval load against a versioned gold set."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, replace
from pathlib import Path

from knowledgeops.config import get_settings
from knowledgeops.evaluation import evaluate_retriever_load, load_evaluation_dataset
from knowledgeops.evaluation.live import build_retrieval_baseline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run KnowledgeOps retrieval load evaluation.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--method", default="hybrid_rerank")
    parser.add_argument("--concurrency", default="10,25,50")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("evaluation-results/load-v0.4.json"))
    return parser.parse_args()


async def run(args: argparse.Namespace) -> Path:
    if args.sample_size < 1:
        raise ValueError("--sample-size must be greater than zero.")
    dataset = load_evaluation_dataset(args.dataset)
    cases = [
        replace(case, knowledge_base_id=args.knowledge_base_id).as_evaluation_case()
        for case in dataset.retrieval_cases[: args.sample_size]
    ]
    levels = [int(value.strip()) for value in args.concurrency.split(",") if value.strip()]
    if not levels or any(level < 1 for level in levels):
        raise ValueError("--concurrency must be a comma-separated list of positive integers.")

    retriever = build_retrieval_baseline(args.method, get_settings())
    try:
        metrics = [
            await evaluate_retriever_load(retriever, cases, concurrency=level)
            for level in levels
        ]
    finally:
        await retriever.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "dataset_version": dataset.dataset_version,
                "method": args.method,
                "sample_size": len(cases),
                "metrics": [asdict(metric) for metric in metrics],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return args.output


if __name__ == "__main__":
    output_path = asyncio.run(run(parse_args()))
    print(f"Wrote {output_path}")
