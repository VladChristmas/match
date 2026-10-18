"""scheduled delivery for agent actions

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_actions",
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_actions",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_agent_actions_next_attempt_at",
        "agent_actions",
        ["next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_actions_next_attempt_at", table_name="agent_actions")
    op.drop_column("agent_actions", "next_attempt_at")
    op.drop_column("agent_actions", "scheduled_at")
