"""Versioned, reviewable contracts for KnowledgeOps offline gold sets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .retrieval import EvaluationCase

EvidenceIdentifier = Literal["chunk_id", "source_name"]
AgentExpectedBehavior = Literal["auto", "direct", "clarify", "tool"]


@dataclass(frozen=True)
class RetrievalGoldCase:
    """A question and its human-validated evidence identifiers."""

    case_id: str
    query: str
    knowledge_base_id: str
    relevant_ids: frozenset[str]
    identifier: EvidenceIdentifier = "chunk_id"
    category: str = "general"

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("Retrieval case ID cannot be empty.")
        if self.identifier not in {"chunk_id", "source_name"}:
            raise ValueError("Unsupported retrieval evidence identifier.")
        EvaluationCase(
            query=self.query,
            knowledge_base_id=self.knowledge_base_id,
            relevant_chunk_ids=self.relevant_ids,
        )

    def as_evaluation_case(self) -> EvaluationCase:
        return EvaluationCase(
            query=self.query,
            knowledge_base_id=self.knowledge_base_id,
            relevant_chunk_ids=self.relevant_ids,
        )


@dataclass(frozen=True)
class AgentGoldCase:
    """A safe, side-effect-free expected Function Calling decision."""

    case_id: str
    user_message: str
    expected_tool_names: tuple[str, ...]
    requires_confirmation: bool = False
    category: str = "general"
    expected_behavior: AgentExpectedBehavior = "auto"
    required_response_keywords: tuple[str, ...] = ()
    conversation_history: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.user_message.strip():
            raise ValueError("Agent case ID and user message cannot be empty.")
        if self.requires_confirmation and self.expected_tool_names != (
            "prepare_ticket_draft",
        ):
            raise ValueError(
                "Confirmation cases must expect prepare_ticket_draft only."
            )
        if self.expected_behavior not in {"auto", "direct", "clarify", "tool"}:
            raise ValueError("Unsupported Agent expected behavior.")
        behavior = self.effective_behavior
        if behavior == "tool" and not self.expected_tool_names:
            raise ValueError("Tool behavior needs at least one expected tool.")
        if behavior != "tool" and self.expected_tool_names:
            raise ValueError("Non-tool behavior cannot expect a tool call.")
        if any(role not in {"user", "assistant"} or not content.strip() for role, content in self.conversation_history):
            raise ValueError("Agent conversation history must contain non-empty user or assistant turns.")

    @property
    def effective_behavior(self) -> Literal["direct", "clarify", "tool"]:
        if self.expected_behavior == "auto":
            return "tool" if self.expected_tool_names else "direct"
        return self.expected_behavior


@dataclass(frozen=True)
class MultiHopGoldCase:
    """A grounded answer requiring multiple named documents or abstention."""

    case_id: str
    question: str
    knowledge_base_id: str
    required_source_names: frozenset[str]
    required_facts: tuple[str, ...]
    should_abstain: bool = False
    category: str = "multi_hop"

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.question.strip():
            raise ValueError("Multi-hop case ID and question cannot be empty.")
        if not self.knowledge_base_id.strip():
            raise ValueError("Multi-hop case knowledge base ID cannot be empty.")
        if self.should_abstain:
            if self.required_source_names or self.required_facts:
                raise ValueError("Abstention cases cannot require sources or facts.")
        elif not self.required_source_names or not self.required_facts:
            raise ValueError("Answerable multi-hop cases need sources and facts.")


@dataclass(frozen=True)
class SecurityGoldCase:
    """A hard business invariant evaluated by API or service integration tests."""

    case_id: str
    scenario: str
    expected_outcome: str
    category: str = "authorization"

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.scenario.strip():
            raise ValueError("Security case ID and scenario cannot be empty.")


@dataclass(frozen=True)
class EvaluationDataset:
    """One immutable logical version of the offline evaluation corpus."""

    schema_version: str
    dataset_version: str
    name: str
    retrieval_cases: tuple[RetrievalGoldCase, ...]
    agent_cases: tuple[AgentGoldCase, ...]
    security_cases: tuple[SecurityGoldCase, ...]
    historical_retrieval_cases: tuple[RetrievalGoldCase, ...] = ()
    multi_hop_cases: tuple[MultiHopGoldCase, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != "knowledgeops-evaluation/v1":
            raise ValueError("Unsupported evaluation dataset schema version.")
        if not self.dataset_version.strip() or not self.name.strip():
            raise ValueError("Evaluation dataset needs a name and version.")
        _ensure_unique_ids(
            [
                *(case.case_id for case in self.retrieval_cases),
                *(case.case_id for case in self.historical_retrieval_cases),
                *(case.case_id for case in self.agent_cases),
                *(case.case_id for case in self.security_cases),
                *(case.case_id for case in self.multi_hop_cases),
            ]
        )


def load_evaluation_dataset(path: str | Path) -> EvaluationDataset:
    """Load a JSON gold set and fail early on incomplete or malformed records."""
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Evaluation dataset does not exist: {source}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Evaluation dataset is not valid JSON: {source}") from error

    if not isinstance(raw, dict):
        raise TypeError("Evaluation dataset root must be an object.")
    return EvaluationDataset(
        schema_version=str(raw.get("schema_version", "")),
        dataset_version=str(raw.get("dataset_version", "")),
        name=str(raw.get("name", "")),
        retrieval_cases=tuple(
            _load_retrieval_case(item) for item in _list_field(raw, "retrieval_cases")
        ),
        agent_cases=tuple(
            _load_agent_case(item) for item in _list_field(raw, "agent_cases")
        ),
        security_cases=tuple(
            _load_security_case(item) for item in _list_field(raw, "security_cases")
        ),
        historical_retrieval_cases=tuple(
            _load_retrieval_case(item)
            for item in _list_field(raw, "historical_retrieval_cases")
        ),
        multi_hop_cases=tuple(
            _load_multi_hop_case(item) for item in _list_field(raw, "multi_hop_cases")
        ),
    )


def _load_retrieval_case(raw: object) -> RetrievalGoldCase:
    item = _object_field(raw, "retrieval case")
    return RetrievalGoldCase(
        case_id=str(item.get("id", "")),
        query=str(item.get("query", "")),
        knowledge_base_id=str(item.get("knowledge_base_id", "")),
        relevant_ids=frozenset(_string_list(item.get("relevant_ids"), "relevant_ids")),
        identifier=str(item.get("identifier", "chunk_id")),  # type: ignore[arg-type]
        category=str(item.get("category", "general")),
    )


def _load_agent_case(raw: object) -> AgentGoldCase:
    item = _object_field(raw, "agent case")
    return AgentGoldCase(
        case_id=str(item.get("id", "")),
        user_message=str(item.get("user_message", "")),
        expected_tool_names=tuple(
            _string_list(item.get("expected_tool_names"), "expected_tool_names")
        ),
        requires_confirmation=bool(item.get("requires_confirmation", False)),
        category=str(item.get("category", "general")),
        expected_behavior=str(item.get("expected_behavior", _default_behavior(item))),  # type: ignore[arg-type]
        required_response_keywords=tuple(
            _string_list(item.get("required_response_keywords", []), "required_response_keywords")
        ),
        conversation_history=_conversation_history(item.get("conversation_history", [])),
    )


def _load_security_case(raw: object) -> SecurityGoldCase:
    item = _object_field(raw, "security case")
    return SecurityGoldCase(
        case_id=str(item.get("id", "")),
        scenario=str(item.get("scenario", "")),
        expected_outcome=str(item.get("expected_outcome", "")),
        category=str(item.get("category", "authorization")),
    )


def _load_multi_hop_case(raw: object) -> MultiHopGoldCase:
    item = _object_field(raw, "multi-hop case")
    return MultiHopGoldCase(
        case_id=str(item.get("id", "")),
        question=str(item.get("question", "")),
        knowledge_base_id=str(item.get("knowledge_base_id", "")),
        required_source_names=frozenset(
            _string_list(item.get("required_source_names", []), "required_source_names")
        ),
        required_facts=tuple(_string_list(item.get("required_facts", []), "required_facts")),
        should_abstain=bool(item.get("should_abstain", False)),
        category=str(item.get("category", "multi_hop")),
    )


def _default_behavior(item: dict[str, object]) -> AgentExpectedBehavior:
    expected_tools = _string_list(item.get("expected_tool_names", []), "expected_tool_names")
    return "tool" if expected_tools else "direct"


def _conversation_history(raw: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, list):
        raise TypeError("conversation_history must be an array.")
    history: list[tuple[str, str]] = []
    for item in raw:
        turn = _object_field(item, "conversation history turn")
        history.append((str(turn.get("role", "")), str(turn.get("content", ""))))
    return tuple(history)


def _list_field(raw: dict[str, object], name: str) -> list[object]:
    value = raw.get(name, [])
    if not isinstance(value, list):
        raise TypeError(f"Evaluation dataset field {name} must be an array.")
    return value


def _object_field(raw: object, label: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise TypeError(f"Evaluation {label} must be an object.")
    return raw


def _string_list(raw: object, name: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"Evaluation field {name} must be an array of strings.")
    return raw


def _ensure_unique_ids(case_ids: list[str]) -> None:
    if any(not case_id.strip() for case_id in case_ids):
        raise ValueError("Evaluation case IDs cannot be empty.")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Evaluation case IDs must be unique across the dataset.")
