"""OpenAI-compatible Function Calling contracts for the enterprise Agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from openai import AsyncOpenAI

from .ticket_intake import assess_ticket_intake

if TYPE_CHECKING:
    from .state import AgentConversationMessage


FUNCTION_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "strict": True,
            "description": (
                "Search the knowledge base currently selected by the employee. "
                "Use this for factual enterprise procedures, troubleshooting, "
                "policies, and document-grounded answers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A concise search query in the employee's language.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_tickets",
            "strict": True,
            "description": (
                "List service tickets belonging to the current employee. "
                "Use this when the employee asks about their tickets, progress, "
                "or work requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_ticket_detail",
            "strict": True,
            "description": (
                "Get the detail of one service ticket that belongs to the current "
                "employee. Use an ID returned by list_my_tickets or supplied by the employee."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The service ticket ID.",
                    }
                },
                "required": ["ticket_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_ticket_draft",
            "strict": True,
            "description": (
                "Prepare a service-ticket draft from the employee's request. "
                "This never creates a ticket: the employee must explicitly confirm "
                "the draft in the application before any write operation occurs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "A concise ticket title.",
                    },
                    "description": {
                        "type": "string",
                        "description": "A clear description of the employee's issue and impact.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "The requested business priority.",
                    },
                    "category": {
                        "type": "string",
                        "description": "A short service category, such as network or access.",
                    },
                    "impact": {
                        "type": "string",
                        "enum": ["single_user", "team", "department", "company"],
                        "description": "The affected business scope.",
                    },
                },
                "required": ["title", "description", "priority", "category", "impact"],
                "additionalProperties": False,
            },
        },
    },
]


@dataclass(frozen=True)
class AgentFunctionCall:
    """One function call selected by the Chat model."""

    id: str
    name: str
    arguments_json: str

    @property
    def arguments(self) -> dict[str, object]:
        parsed = json.loads(self.arguments_json or "{}")
        if not isinstance(parsed, dict):
            raise TypeError("Function arguments must be a JSON object.")
        return parsed


@dataclass(frozen=True)
class AgentModelResponse:
    """A model turn before or after the server executes a function."""

    content: str | None
    tool_calls: list[AgentFunctionCall]

    def as_assistant_message(self) -> dict[str, object]:
        """Translate the parsed tool turn back to the provider wire format."""
        return {
            "role": "assistant",
            "content": self.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments_json,
                    },
                }
                for call in self.tool_calls
            ],
        }


class FunctionCallingAgent(Protocol):
    """Minimal provider boundary used by the LangGraph workflow."""

    async def complete(
        self,
        messages: list[dict[str, object]],
        *,
        tool_choice: str = "auto",
    ) -> AgentModelResponse:
        """Generate text or request one of the declared functions."""


class OpenAIFunctionCallingAgent:
    """Use the portable OpenAI Chat Completions Function Calling protocol."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        model: str,
        temperature: float = 0,
    ) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature

    async def complete(
        self,
        messages: list[dict[str, object]],
        *,
        tool_choice: str = "auto",
    ) -> AgentModelResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            tools=FUNCTION_DEFINITIONS,
            tool_choice=tool_choice,
            parallel_tool_calls=False,
        )
        message = response.choices[0].message
        tool_calls = []
        for call in message.tool_calls or []:
            function = call.function
            tool_calls.append(
                AgentFunctionCall(
                    id=call.id,
                    name=function.name,
                    arguments_json=function.arguments or "{}",
                )
            )
        return AgentModelResponse(content=message.content, tool_calls=tool_calls)


class TicketIntakeGuardedFunctionCallingAgent:
    """Prevent a model from inventing missing facts for a ticket draft."""

    def __init__(self, delegate: FunctionCallingAgent) -> None:
        self.delegate = delegate

    async def complete(
        self,
        messages: list[dict[str, object]],
        *,
        tool_choice: str = "auto",
    ) -> AgentModelResponse:
        assessment = assess_ticket_intake(
            str(message["content"])
            for message in messages
            if message.get("role") == "user" and isinstance(message.get("content"), str)
        )
        if assessment.requires_clarification:
            return AgentModelResponse(
                content=assessment.clarification_message,
                tool_calls=[],
            )
        return await self.delegate.complete(messages, tool_choice=tool_choice)


def build_function_call_messages(
    *,
    user_message: str,
    conversation_history: list[AgentConversationMessage],
) -> list[dict[str, object]]:
    """Create bounded context and explicit safety rules for an Agent turn."""
    return [
        {
            "role": "system",
            "content": (
                "You are KnowledgeOps, an enterprise knowledge-base and service-desk "
                "assistant. Reply in concise Chinese. Use a function whenever the "
                "employee requests factual knowledge-base content or ticket data; do "
                "not invent internal information or ticket status. The server enforces "
                "employee data scope. For a new ticket, call prepare_ticket_draft only "
                "after collecting enough employee-provided information. Before drafting, "
                "the employee must state a concrete issue, operational context (for example "
                "an error, time, device, or attempted action), and business impact. Never "
                "infer those facts or use a function when any of them is missing; ask the "
                "employee to supplement the report instead. It creates no data: the employee "
                "must confirm the draft in the application. Never claim a ticket was "
                "created until the server reports a confirmed result. For ordinary "
                "conversation, answer directly without a function."
            ),
        },
        *[
            {"role": message.role, "content": message.content}
            for message in conversation_history[-8:]
        ],
        {"role": "user", "content": user_message},
    ]
