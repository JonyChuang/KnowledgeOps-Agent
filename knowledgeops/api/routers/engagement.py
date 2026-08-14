"""Personal workspace and global-search endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import WorkspaceItemType
from ...schemas import (
    AgentFeedbackCreate,
    AgentFeedbackRead,
    GlobalSearchItemRead,
    GlobalSearchRead,
    WorkspaceItemCreate,
    WorkspaceItemListRead,
    WorkspaceItemRead,
)
from ...services import EngagementService, ResourceNotFoundError
from ..dependencies import get_actor, get_session

engagement_router = APIRouter(tags=["engagement"])


@engagement_router.get("/search", response_model=GlobalSearchRead)
async def global_search(
    query: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> GlobalSearchRead:
    """Search local documents, graph entities, employee tickets, and conversations."""
    items = await EngagementService(session).global_search(
        query,
        actor=actor,
        limit=limit,
    )
    return GlobalSearchRead(
        query=query,
        items=[GlobalSearchItemRead(**item.__dict__) for item in items],
        total=len(items),
    )


@engagement_router.get("/favorites", response_model=WorkspaceItemListRead)
async def list_favorites(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> WorkspaceItemListRead:
    """List the current employee's saved workspace shortcuts."""
    items = await EngagementService(session).list_favorites(actor=actor, limit=limit)
    return WorkspaceItemListRead(
        items=[WorkspaceItemRead.model_validate(item) for item in items]
    )


@engagement_router.post("/favorites", response_model=WorkspaceItemRead, status_code=201)
async def add_favorite(
    payload: WorkspaceItemCreate,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> WorkspaceItemRead:
    """Save one employee-owned shortcut; duplicates are idempotent."""
    item = await EngagementService(session).add_favorite(payload, actor=actor)
    return WorkspaceItemRead.model_validate(item)


@engagement_router.delete("/favorites/{entity_type}/{entity_id}", status_code=204)
async def remove_favorite(
    entity_type: WorkspaceItemType,
    entity_id: str,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> None:
    """Remove only the current employee's matching shortcut."""
    try:
        await EngagementService(session).remove_favorite(
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@engagement_router.get("/recent-visits", response_model=WorkspaceItemListRead)
async def list_recent_visits(
    limit: int = Query(default=12, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> WorkspaceItemListRead:
    """List the current employee's most recently opened workspace items."""
    items = await EngagementService(session).list_recent_visits(actor=actor, limit=limit)
    return WorkspaceItemListRead(
        items=[WorkspaceItemRead.model_validate(item) for item in items]
    )


@engagement_router.post("/recent-visits", response_model=WorkspaceItemRead, status_code=201)
async def record_recent_visit(
    payload: WorkspaceItemCreate,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> WorkspaceItemRead:
    """Record or refresh one employee-object visit without duplicate rows."""
    item = await EngagementService(session).record_recent_visit(payload, actor=actor)
    return WorkspaceItemRead.model_validate(item)


@engagement_router.post(
    "/agent-messages/{agent_message_id}/feedback",
    response_model=AgentFeedbackRead,
)
async def submit_agent_feedback(
    agent_message_id: str,
    payload: AgentFeedbackCreate,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> AgentFeedbackRead:
    """Save one employee's latest feedback on one persisted Agent response."""
    try:
        feedback = await EngagementService(session).add_agent_feedback(
            agent_message_id,
            payload,
            actor=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return AgentFeedbackRead.model_validate(feedback)
