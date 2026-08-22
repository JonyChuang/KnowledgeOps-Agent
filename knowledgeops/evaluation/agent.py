"""Offline checks for the model's Function Calling decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..agents.function_calling import (
    FUNCTION_DEFINITIONS,
    FunctionCallingAgent,
    build_function_call_messages,
)
from ..agents.state import AgentConversationMessage
from .datasets import AgentGoldCase


@dataclass(frozen=True)
class AgentCaseResult:
    case_id: str
    expected_behavior: str
    expected_tool_names: tuple[str, ...]
    actual_tool_names: tuple[str, ...]
    tool_selection_passed: bool
    response_behavior_passed: bool
    valid_argument_count: int
    tool_call_count: int
    confirmation_guard_passed: bool | None


@dataclass(frozen=True)
class FunctionCallingMetrics:
    evaluated_cases: int
    exact_tool_selection_accuracy: float
    valid_tool_argument_rate: float
    confirmation_guard_rate: float | None
    clarification_rate: float | None
    results: tuple[AgentCaseResult, ...]


async def evaluate_function_calling_agent(
    agent: FunctionCallingAgent,
    cases: list[AgentGoldCase] | tuple[AgentGoldCase, ...],
) -> FunctionCallingMetrics:
    """Evaluate tool selection without executing any business-side effects.

    The evaluator sends only the initial model request. A request to draft a
    ticket is measured as a model decision; it never reaches the ticket write
    node, so this evaluation can run against a configured production model.
    """
    if not cases:
        raise ValueError("Agent evaluation cases cannot be empty.")

    results: list[AgentCaseResult] = []
    total_tool_calls = 0
    valid_tool_calls = 0
    selection_passes = 0
    confirmation_cases = 0
    confirmation_passes = 0
    clarification_cases = 0
    clarification_passes = 0

    for case in cases:
        response = await agent.complete(
            build_function_call_messages(
                user_message=case.user_message,
                conversation_history=[
                    AgentConversationMessage(role=role, content=content)
                    for role, content in case.conversation_history
                ],
            )
        )
        actual_tool_names = tuple(call.name for call in response.tool_calls)
        selection_passed = actual_tool_names == case.expected_tool_names
        selection_passes += int(selection_passed)
        response_behavior_passed = _response_behavior_passed(case, response.content)
        if case.effective_behavior == "clarify":
            clarification_cases += 1
            clarification_passes += int(selection_passed and response_behavior_passed)

        valid_arguments = sum(
            _has_valid_arguments(call.name, call.arguments_json)
            for call in response.tool_calls
        )
        total_tool_calls += len(response.tool_calls)
        valid_tool_calls += valid_arguments

        confirmation_passed: bool | None = None
        if case.requires_confirmation:
            confirmation_cases += 1
            confirmation_passed = actual_tool_names == (
                "prepare_ticket_draft",
            ) and valid_arguments == 1
            confirmation_passes += int(confirmation_passed)

        results.append(
            AgentCaseResult(
                case_id=case.case_id,
                expected_behavior=case.effective_behavior,
                expected_tool_names=case.expected_tool_names,
                actual_tool_names=actual_tool_names,
                tool_selection_passed=selection_passed,
                response_behavior_passed=response_behavior_passed,
                valid_argument_count=valid_arguments,
                tool_call_count=len(response.tool_calls),
                confirmation_guard_passed=confirmation_passed,
            )
        )

    return FunctionCallingMetrics(
        evaluated_cases=len(cases),
        exact_tool_selection_accuracy=selection_passes / len(cases),
        valid_tool_argument_rate=(
            valid_tool_calls / total_tool_calls if total_tool_calls else 1.0
        ),
        confirmation_guard_rate=(
            confirmation_passes / confirmation_cases if confirmation_cases else None
        ),
        clarification_rate=(
            clarification_passes / clarification_cases if clarification_cases else None
        ),
        results=tuple(results),
    )


def _response_behavior_passed(case: AgentGoldCase, content: str | None) -> bool:
    """Check non-tool response intent without treating prose as a factual answer."""
    if case.effective_behavior == "tool":
        return True
    text = (content or "").strip()
    if not text:
        return False
    if case.effective_behavior == "direct":
        return True
    return all(keyword.casefold() in text.casefold() for keyword in case.required_response_keywords)


def _has_valid_arguments(name: str, arguments_json: str) -> bool:
    definition = _function_definitions_by_name().get(name)
    if definition is None:
        return False
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return False
    if not isinstance(arguments, dict):
        return False

    parameters = definition["parameters"]
    properties = parameters["properties"]
    required = set(parameters.get("required", []))
    if not required.issubset(arguments) or set(arguments).difference(properties):
        return False

    for field_name, value in arguments.items():
        field = properties[field_name]
        if field.get("type") == "string" and not isinstance(value, str):
            return False
        if "enum" in field and value not in field["enum"]:
            return False
    return True


def _function_definitions_by_name() -> dict[str, dict[str, Any]]:
    return {
        str(definition["function"]["name"]): definition["function"]
        for definition in FUNCTION_DEFINITIONS
    }
