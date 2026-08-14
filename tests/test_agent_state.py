import json

import pytest
from pydantic import ValidationError

from knowledgeops.agents.state import (
    AgentIntent,
    AgentState,
    ConfirmationStatus,
    PendingAction,
)


@pytest.mark.parametrize("intent", list(AgentIntent))
def test_agent_state_serializes_each_supported_intent(
    intent: AgentIntent,
) -> None:
    state = AgentState(
        actor="alice",
        user_message="请处理我的请求",
        intent=intent,
    )

    payload = json.loads(state.model_dump_json())

    assert payload["intent"] == intent.value


@pytest.mark.parametrize(
    "intent",
    [
        AgentIntent.KNOWLEDGE_QA,
        AgentIntent.TICKET_QUERY,
    ],
)
def test_read_only_intents_cannot_create_tickets(
    intent: AgentIntent,
) -> None:
    state = AgentState(
        actor="alice",
        user_message="查询信息",
        intent=intent,
    )

    assert state.can_create_ticket is False


@pytest.mark.parametrize(
    ("confirmation_status", "expected"),
    [
        (ConfirmationStatus.PENDING, False),
        (ConfirmationStatus.REJECTED, False),
        (ConfirmationStatus.CONFIRMED, True),
    ],
)
def test_ticket_creation_requires_explicit_confirmation(
    confirmation_status: ConfirmationStatus,
    expected: bool,
) -> None:
    state = AgentState(
        actor="alice",
        user_message="创建一个工单",
        intent=AgentIntent.TICKET_CREATE,
        pending_action=PendingAction(
            action_type="ticket.create",
            arguments={"title": "登录失败"},
        ),
        confirmation_status=confirmation_status,
    )

    assert state.can_create_ticket is expected


def test_created_ticket_id_requires_confirmed_ticket_action() -> None:
    with pytest.raises(ValidationError):
        AgentState(
            actor="alice",
            user_message="创建一个工单",
            intent=AgentIntent.TICKET_CREATE,
            pending_action=PendingAction(
                action_type="ticket.create",
                arguments={"title": "登录失败"},
            ),
            confirmation_status=ConfirmationStatus.PENDING,
            created_ticket_id="ticket-001",
        )