"""add persistent agent conversations

Revision ID: a8105c4e7b2d
Revises: f22e63c3d0af
Create Date: 2026-08-13 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a8105c4e7b2d"
down_revision: Union[str, Sequence[str], None] = "f22e63c3d0af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("agent_conversations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_agent_conversations_actor"),
            ["actor"],
            unique=False,
        )

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("turn_id", sa.String(length=36), nullable=True),
        sa.Column("turn_status", sa.String(length=32), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("pending_action", sa.JSON(), nullable=True),
        sa.Column("created_ticket_id", sa.String(length=36), nullable=True),
        sa.Column("ticket_ids", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_agent_message_sequence",
        ),
        sa.UniqueConstraint("turn_id"),
    )
    with op.batch_alter_table("agent_messages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_agent_messages_conversation_id"),
            ["conversation_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_messages_turn_id"),
            ["turn_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_messages_turn_id"))
        batch_op.drop_index(batch_op.f("ix_agent_messages_conversation_id"))
    op.drop_table("agent_messages")

    with op.batch_alter_table("agent_conversations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_conversations_actor"))
    op.drop_table("agent_conversations")
