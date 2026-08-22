"""Machine-readable and Markdown reporting for offline evaluation runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .agent import FunctionCallingMetrics
from .answers import MultiHopAnswerMetrics
from .datasets import EvaluationDataset
from .retrieval import ArchiveIsolationMetrics, RetrievalMetrics
from .verifier import VerifierMetrics


def render_evaluation_report(
    dataset: EvaluationDataset,
    *,
    retrieval_metrics: Mapping[str, RetrievalMetrics] | None = None,
    historical_retrieval_metrics: Mapping[str, RetrievalMetrics] | None = None,
    archive_isolation_metrics: Mapping[str, ArchiveIsolationMetrics] | None = None,
    function_calling_metrics: FunctionCallingMetrics | None = None,
    multi_hop_metrics: MultiHopAnswerMetrics | None = None,
    verifier_metrics: VerifierMetrics | None = None,
) -> str:
    """Render only measured values; absent runs remain explicit TBD entries."""
    retrieval_metrics = retrieval_metrics or {}
    historical_retrieval_metrics = historical_retrieval_metrics or {}
    archive_isolation_metrics = archive_isolation_metrics or {}
    generated_at = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# KnowledgeOps Offline Evaluation: {dataset.name}",
        "",
        f"- Dataset version: `{dataset.dataset_version}`",
        f"- Generated at: `{generated_at}`",
        f"- Current retrieval cases: {len(dataset.retrieval_cases)}",
        f"- Historical retrieval cases: {len(dataset.historical_retrieval_cases)}",
        f"- Agent cases: {len(dataset.agent_cases)}",
        f"- Security invariants: {len(dataset.security_cases)}",
        f"- Multi-hop answer cases: {len(dataset.multi_hop_cases)}",
        "",
        "## Current Knowledge Retrieval",
        "",
        "| Method | Queries | Recall@k | MRR | nDCG@k | Avg latency (ms) | P50 (ms) | P95 (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if retrieval_metrics:
        for method, metrics in retrieval_metrics.items():
            lines.append(
                f"| {method} | {metrics.evaluated_queries} | "
                f"{metrics.recall_at_k:.4f} | {metrics.mrr:.4f} | "
                f"{metrics.ndcg_at_k:.4f} | {metrics.average_latency_ms:.2f} | "
                f"{metrics.p50_latency_ms:.2f} | {metrics.p95_latency_ms:.2f} |"
            )
    else:
        lines.append("| No measured run | TBD | TBD | TBD | TBD | TBD | TBD | TBD |")

    lines.extend(
        [
            "",
            "## Archive Governance",
            "",
            (
                "Historical retrieval runs only when a user explicitly enables historical sources. "
                "Archive isolation sends the same queries through normal employee retrieval; "
                "a leakage rate of 0 means no archived source was exposed."
            ),
            "",
            "| Method | Historical queries | Historical Recall@k | Historical MRR | Archive isolation queries | Archive leakage rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    methods = set(historical_retrieval_metrics).union(archive_isolation_metrics)
    if methods:
        for method in sorted(methods):
            historical = historical_retrieval_metrics.get(method)
            isolation = archive_isolation_metrics.get(method)
            lines.append(
                "| {method} | {historical_queries} | {historical_recall} | {historical_mrr} | "
                "{isolation_queries} | {leakage_rate} |".format(
                    method=method,
                    historical_queries=(
                        historical.evaluated_queries if historical is not None else "TBD"
                    ),
                    historical_recall=(
                        f"{historical.recall_at_k:.4f}" if historical is not None else "TBD"
                    ),
                    historical_mrr=(
                        f"{historical.mrr:.4f}" if historical is not None else "TBD"
                    ),
                    isolation_queries=(
                        isolation.evaluated_queries if isolation is not None else "TBD"
                    ),
                    leakage_rate=(
                        f"{isolation.archive_leakage_rate:.4f}"
                        if isolation is not None
                        else "TBD"
                    ),
                )
            )
    else:
        lines.append("| No historical-retrieval cases | N/A | N/A | N/A | N/A | N/A |")

    lines.extend(
        [
            "",
            "## Function Calling",
            "",
            "| Cases | Exact tool selection | Valid arguments | Draft selection | Clarification behavior |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    if function_calling_metrics is None:
        lines.append("| TBD | TBD | TBD | TBD | TBD |")
    else:
        confirmation = function_calling_metrics.confirmation_guard_rate
        lines.append(
            "| {cases} | {selection:.4f} | {arguments:.4f} | {confirmation} | {clarification} |".format(
                cases=function_calling_metrics.evaluated_cases,
                selection=function_calling_metrics.exact_tool_selection_accuracy,
                arguments=function_calling_metrics.valid_tool_argument_rate,
                confirmation=(f"{confirmation:.4f}" if confirmation is not None else "N/A"),
                clarification=(
                    f"{function_calling_metrics.clarification_rate:.4f}"
                    if function_calling_metrics.clarification_rate is not None
                    else "N/A"
                ),
            )
        )

    lines.extend(
        [
            "",
            "## Multi-hop Grounded Answers",
            "",
            "| Cases | Evidence Recall@k | Evidence precision@k | Fact recall | Fully grounded answers | Grounded abstention | Avg latency (ms) | P95 (ms) |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    if multi_hop_metrics is None:
        lines.append("| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |")
    else:
        lines.append(
            f"| {multi_hop_metrics.evaluated_cases} | {_format_rate(multi_hop_metrics.evidence_recall_at_k)} | {_format_rate(multi_hop_metrics.evidence_precision_at_k)} | {_format_rate(multi_hop_metrics.answer_fact_recall)} | {_format_rate(multi_hop_metrics.fully_grounded_answer_rate)} | {_format_rate(multi_hop_metrics.grounded_abstention_rate)} | {multi_hop_metrics.average_latency_ms:.2f} | {multi_hop_metrics.p95_latency_ms:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Independent Verifier",
            "",
            "| Cases | Agreement with deterministic gold | False accept rate | False reject rate |",
            "| ---: | ---: | ---: | ---: |",
        ]
    )
    if verifier_metrics is None:
        lines.append("| TBD | TBD | TBD | TBD |")
    else:
        lines.append(
            f"| {verifier_metrics.evaluated_cases} | {verifier_metrics.agreement_with_gold:.4f} | {_format_rate(verifier_metrics.false_accept_rate)} | {_format_rate(verifier_metrics.false_reject_rate)} |"
        )

    lines.extend(
        [
            "",
            "## Security Gates",
            "",
            (
                "The following invariants must be verified by API/service integration tests: "
                "no unconfirmed ticket write, no cross-employee ticket read, and no unauthorized service-desk action."
            ),
            "",
            "No scores are invented in this report. TBD means that the corresponding run has not executed.",
            "",
        ]
    )
    return "\n".join(lines)


def write_evaluation_report(
    output_directory: str | Path,
    dataset: EvaluationDataset,
    *,
    retrieval_metrics: Mapping[str, RetrievalMetrics] | None = None,
    historical_retrieval_metrics: Mapping[str, RetrievalMetrics] | None = None,
    archive_isolation_metrics: Mapping[str, ArchiveIsolationMetrics] | None = None,
    function_calling_metrics: FunctionCallingMetrics | None = None,
    multi_hop_metrics: MultiHopAnswerMetrics | None = None,
    verifier_metrics: VerifierMetrics | None = None,
) -> tuple[Path, Path]:
    """Write an auditable Markdown summary and its JSON source values."""
    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "report.md"
    json_path = destination / "report.json"
    report_path.write_text(
        render_evaluation_report(
            dataset,
            retrieval_metrics=retrieval_metrics,
            historical_retrieval_metrics=historical_retrieval_metrics,
            archive_isolation_metrics=archive_isolation_metrics,
            function_calling_metrics=function_calling_metrics,
            multi_hop_metrics=multi_hop_metrics,
            verifier_metrics=verifier_metrics,
        ),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            {
                "dataset_version": dataset.dataset_version,
                "retrieval_metrics": {
                    name: asdict(metrics)
                    for name, metrics in (retrieval_metrics or {}).items()
                },
                "historical_retrieval_metrics": {
                    name: asdict(metrics)
                    for name, metrics in (historical_retrieval_metrics or {}).items()
                },
                "archive_isolation_metrics": {
                    name: asdict(metrics)
                    for name, metrics in (archive_isolation_metrics or {}).items()
                },
                "function_calling_metrics": (
                    asdict(function_calling_metrics)
                    if function_calling_metrics is not None
                    else None
                ),
                "multi_hop_metrics": (
                    asdict(multi_hop_metrics) if multi_hop_metrics is not None else None
                ),
                "verifier_metrics": (
                    asdict(verifier_metrics) if verifier_metrics is not None else None
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path, json_path


def _format_rate(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "N/A"
