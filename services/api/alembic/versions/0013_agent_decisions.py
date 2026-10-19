"""agent decision loop records

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("escalation_reason", sa.String(length=64), nullable=True),
        sa.Column("missing", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_id"], ["agent_actions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_decisions_user_id", "agent_decisions", ["user_id"])
    op.create_index("ix_agent_decisions_conversation_id", "agent_decisions", ["conversation_id"])
    op.create_index("ix_agent_decisions_action_id", "agent_decisions", ["action_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_decisions_action_id", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_conversation_id", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_user_id", table_name="agent_decisions")
    op.drop_table("agent_decisions")
