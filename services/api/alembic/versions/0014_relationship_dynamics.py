"""relationship dynamics signals and timeline

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "relationship_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relationship_signals_user_id", "relationship_signals", ["user_id"])
    op.create_index(
        "ix_relationship_signals_conversation_id", "relationship_signals", ["conversation_id"]
    )
    op.create_index("ix_relationship_signals_dimension", "relationship_signals", ["dimension"])
    op.create_index("ix_relationship_signals_observed_at", "relationship_signals", ["observed_at"])

    op.create_table(
        "relationship_timeline",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("signals_before", sa.JSON(), nullable=False),
        sa.Column("signals_after", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relationship_timeline_user_id", "relationship_timeline", ["user_id"])
    op.create_index(
        "ix_relationship_timeline_conversation_id",
        "relationship_timeline",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_relationship_timeline_conversation_id", table_name="relationship_timeline")
    op.drop_index("ix_relationship_timeline_user_id", table_name="relationship_timeline")
    op.drop_table("relationship_timeline")
    op.drop_index("ix_relationship_signals_observed_at", table_name="relationship_signals")
    op.drop_index("ix_relationship_signals_dimension", table_name="relationship_signals")
    op.drop_index("ix_relationship_signals_conversation_id", table_name="relationship_signals")
    op.drop_index("ix_relationship_signals_user_id", table_name="relationship_signals")
    op.drop_table("relationship_signals")
