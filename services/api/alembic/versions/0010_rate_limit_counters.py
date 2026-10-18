"""rate limit counters

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_counters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("key", "window_start", name="uq_rate_limit_counters_key_window"),
    )
    op.create_index("ix_rate_limit_counters_key", "rate_limit_counters", ["key"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_counters_key", table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
