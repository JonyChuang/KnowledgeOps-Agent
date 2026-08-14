"""add favorites visits and agent feedback

Revision ID: b76e2d4a9c31
Revises: f91b3d2e8a45
Create Date: 2026-08-13 19:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b76e2d4a9c31"
down_revision: str | Sequence[str] | None = "f91b3d2e8a45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    workspace_item_type = sa.Enum(
        "knowledge_base",
        "document",
        "graph",
        "ticket",
        "conversation",
        name="workspace_item_type",
        native_enum=False,
    )
    op.create_table(
        "favorites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("entity_type", workspace_item_type, nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=False),
        sa.Column("target_view", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor", "entity_type", "entity_id", name="uq_favorite_actor_entity"),
    )
    op.create_index("ix_favorites_actor", "favorites", ["actor"])
    op.create_index("ix_favorites_entity_type", "favorites", ["entity_type"])
    op.create_index("ix_favorites_entity_id", "favorites", ["entity_id"])

    op.create_table(
        "recent_visits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum(
                "knowledge_base",
                "document",
                "graph",
                "ticket",
                "conversation",
                name="workspace_item_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=False),
        sa.Column("target_view", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor", "entity_type", "entity_id", name="uq_recent_visit_actor_entity"),
    )
    op.create_index("ix_recent_visits_actor", "recent_visits", ["actor"])
    op.create_index("ix_recent_visits_entity_type", "recent_visits", ["entity_type"])
    op.create_index("ix_recent_visits_entity_id", "recent_visits", ["entity_id"])
    op.create_index("ix_recent_visits_visited_at", "recent_visits", ["visited_at"])

    op.create_table(
        "agent_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("agent_message_id", sa.String(length=36), nullable=False),
        sa.Column(
            "feedback_type",
            sa.Enum(
                "helpful",
                "unhelpful",
                "stale_citation",
                "incorrect_answer",
                name="agent_feedback_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "reviewed", "resolved", name="agent_feedback_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_message_id"], ["agent_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor", "agent_message_id", name="uq_agent_feedback_actor_message"),
    )
    op.create_index("ix_agent_feedback_actor", "agent_feedback", ["actor"])
    op.create_index("ix_agent_feedback_agent_message_id", "agent_feedback", ["agent_message_id"])
    op.create_index("ix_agent_feedback_feedback_type", "agent_feedback", ["feedback_type"])
    op.create_index("ix_agent_feedback_status", "agent_feedback", ["status"])


def downgrade() -> None:
    op.drop_table("agent_feedback")
    op.drop_table("recent_visits")
    op.drop_table("favorites")
