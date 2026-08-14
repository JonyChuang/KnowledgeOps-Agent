"""HTTP contracts for global search, favorites, visits, and Agent feedback."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models import AgentFeedbackStatus, AgentFeedbackType, WorkspaceItemType


class WorkspaceItemCreate(BaseModel):
    """A client-side navigation target persisted for one employee."""

    entity_type: WorkspaceItemType
    entity_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=255)
    subtitle: str = Field(default="", max_length=4_000)
    target_view: str = Field(min_length=1, max_length=40)
    target_id: str | None = Field(default=None, max_length=120)
    metadata_json: dict[str, object] = Field(default_factory=dict)


class WorkspaceItemRead(BaseModel):
    """A favorite or recent visit returned to its owning employee."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: WorkspaceItemType
    entity_id: str
    title: str
    subtitle: str
    target_view: str
    target_id: str | None = None
    metadata_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    visited_at: datetime | None = None


class WorkspaceItemListRead(BaseModel):
    items: list[WorkspaceItemRead] = Field(default_factory=list)


class GlobalSearchItemRead(BaseModel):
    """One type-labelled result from the local cross-workspace search index."""

    entity_type: WorkspaceItemType
    entity_id: str
    title: str
    summary: str
    target_view: str
    target_id: str | None = None
    metadata_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime | None = None


class GlobalSearchRead(BaseModel):
    query: str
    items: list[GlobalSearchItemRead] = Field(default_factory=list)
    total: int = Field(ge=0)


class AgentFeedbackCreate(BaseModel):
    feedback_type: AgentFeedbackType
    comment: str = Field(default="", max_length=2_000)


class AgentFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_message_id: str
    feedback_type: AgentFeedbackType
    comment: str
    status: AgentFeedbackStatus
    created_at: datetime
    updated_at: datetime
