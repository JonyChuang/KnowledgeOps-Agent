# Phase 29: Archive-Aware Evaluation Governance

## Problem

The first v0.4 report measured all 800 document queries as ordinary employee retrieval. That included 200 queries whose only correct evidence was an archived document. This conflicts with the product contract: archived sources are retained for audit but must not appear in normal employee answers.

The resulting `Recall@5=75%` was therefore not a valid measure of day-to-day retrieval quality. Raising that score by returning archived sources would create a real enterprise risk: outdated procedures could be cited as current instructions.

## Design

v0.4 remains unchanged as the historical record. The corrected dataset is `v0.4.1` and separates three claims:

| Scenario | Source visibility | Metric meaning |
| --- | --- | --- |
| Current knowledge retrieval | Active only | Whether an employee can find the approved policy, procedure, or exception. |
| Historical retrieval | Active plus archived, explicitly enabled | Whether an auditor can trace a historical source. |
| Archive isolation | Active only | Whether an archived source leaks into an employee search. `0` is the desired leakage rate. |

The corrected dataset keeps the same 40 topics and 800 retrieval questions, but divides them into 600 current-source questions and 200 archive-history questions. Historical questions are deliberately phrased as audit or history requests rather than asking for a contradictory "current archived" document.

## Implementation

- `EvaluationDataset` now optionally contains `historical_retrieval_cases`.
- `evaluate_retriever(..., include_archived=True)` runs only in explicit history mode.
- `evaluate_archive_isolation` sends the same history-oriented questions through ordinary retrieval and records the fraction of queries that exposed any `archived` result.
- Evaluation adapters now preserve document lifecycle metadata across vector, BM25, hybrid, and graph baselines.
- The report has separate **Current Knowledge Retrieval** and **Archive Governance** sections. It never combines these distinct operating modes into one Recall value.

## Interview Explanation

"I treated archive state as a retrieval authorization boundary, not as a filename convention. The offline evaluation originally penalized that boundary by requiring archived sources in normal search. I corrected the benchmark by separating current-user recall, explicit history recall, and archive leakage. This lets us optimize relevance without rewarding unsafe exposure of obsolete enterprise procedures."

## Verification

The unit tests cover explicit history retrieval, archive-leak detection, dataset counts, and report serialization. The next live run should use `knowledgeops-gold-v0.4.1.json`; it does not require re-uploading or re-indexing the v0.4 knowledge base.
