"""compatibility and risk assessments

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "compatibility_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("goals_alignment", sa.Float(), nullable=False),
        sa.Column("values_alignment", sa.Float(), nullable=False),
        sa.Column("lifestyle_alignment", sa.Float(), nullable=False),
        sa.Column("reciprocity", sa.Float(), nullable=False),
        sa.Column("uncertainty", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "model_version",
            sa.String(length=64),
            nullable=False,
            server_default="heuristic-1.0",
        ),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_compatibility_assessments_user_id", "compatibility_assessments", ["user_id"]
    )
    op.create_index(
        "ix_compatibility_assessments_match_id", "compatibility_assessments", ["match_id"]
    )
    op.create_index(
        "ix_compatibility_assessments_conversation_id",
        "compatibility_assessments",
        ["conversation_id"],
    )

    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("risk_category", sa.String(length=64), nullable=False),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("recommended_action", sa.String(length=64), nullable=False),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_risk_assessments_user_id", "risk_assessments", ["user_id"])
    op.create_index("ix_risk_assessments_match_id", "risk_assessments", ["match_id"])
    op.create_index("ix_risk_assessments_conversation_id", "risk_assessments", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_risk_assessments_conversation_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_match_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_user_id", table_name="risk_assessments")
    op.drop_table("risk_assessments")

    op.drop_index(
        "ix_compatibility_assessments_conversation_id",
        table_name="compatibility_assessments",
    )
    op.drop_index("ix_compatibility_assessments_match_id", table_name="compatibility_assessments")
    op.drop_index("ix_compatibility_assessments_user_id", table_name="compatibility_assessments")
    op.drop_table("compatibility_assessments")
