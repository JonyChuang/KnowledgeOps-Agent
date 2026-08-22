"""Deterministic retrieval plans for explicit multi-source questions."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceFacet:
    """One document role the employee explicitly asks the system to combine."""

    name: str
    query_suffix: str


@dataclass(frozen=True)
class MultiSourceQueryPlan:
    """The main question plus focused recalls for each named evidence role."""

    primary_query: str
    facet_queries: tuple[tuple[EvidenceFacet, str], ...]

    @property
    def is_multi_source(self) -> bool:
        return bool(self.facet_queries)


_EVIDENCE_FACETS: tuple[tuple[EvidenceFacet, re.Pattern[str]], ...] = (
    (
        EvidenceFacet(name="policy", query_suffix="制度 policy"),
        re.compile(r"\bpolicy\b|政策|制度|规范", re.IGNORECASE),
    ),
    (
        EvidenceFacet(name="procedure", query_suffix="流程 procedure"),
        re.compile(r"\bprocedure\b|流程|操作步骤", re.IGNORECASE),
    ),
    (
        EvidenceFacet(name="exception", query_suffix="例外 exception"),
        re.compile(r"\bexception\b|例外|豁免", re.IGNORECASE),
    ),
    (
        EvidenceFacet(name="runbook", query_suffix="手册 runbook"),
        re.compile(r"\brunbook\b|手册|预案", re.IGNORECASE),
    ),
)
_ROLE_TERMS_PATTERN = re.compile(
    r"\b(?:policy|procedure|exception|runbook)\b|政策|制度|规范|流程|操作步骤|例外|豁免|手册|预案",
    re.IGNORECASE,
)
_QUERY_JOINERS_PATTERN = re.compile(
    r"\b(?:and|or|combine|with)\b|以及|及|和|与|并且|结合",
    re.IGNORECASE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


def build_multi_source_query_plan(query: str) -> MultiSourceQueryPlan:
    """Expand only questions that explicitly request two or more source roles.

    The planner does not try to infer a document type from source names or answer
    a question itself. It simply preserves the user's explicit request for, for
    example, a policy and a procedure, and issues one focused recall for each.
    """
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("Query cannot be empty.")

    requested_facets = tuple(
        facet
        for facet, pattern in _EVIDENCE_FACETS
        if pattern.search(clean_query)
    )
    if len(requested_facets) < 2:
        return MultiSourceQueryPlan(primary_query=clean_query, facet_queries=())

    topic_query = _normalize_topic_query(clean_query)
    return MultiSourceQueryPlan(
        primary_query=clean_query,
        facet_queries=tuple(
            (facet, f"{topic_query} {facet.query_suffix}".strip())
            for facet in requested_facets
        ),
    )


def _normalize_topic_query(query: str) -> str:
    without_roles = _ROLE_TERMS_PATTERN.sub(" ", query)
    without_joiners = _QUERY_JOINERS_PATTERN.sub(" ", without_roles)
    normalized = _WHITESPACE_PATTERN.sub(" ", without_joiners).strip(" ,;:：，；")
    return normalized if len(normalized) >= 3 else query
