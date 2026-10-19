"""adaptive autonomy budgets and calibration rules

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "autonomy_budgets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("max_messages_per_day", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("active_start_hour", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("active_end_hour", sa.Integer(), nullable=False, server_default="23"),
        sa.Column("allowed_conversation_ids", sa.JSON(), nullable=False),
        sa.Column("actions_always_confirm", sa.JSON(), nullable=False),
        sa.Column("auto_stop_after_errors", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("consecutive_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("global_paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_autonomy_budgets_user_id"),
    )

    op.create_table(
        "autonomy_error_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("action_id", sa.Uuid(), nullable=True),
        sa.Column("error_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_id"], ["agent_actions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_autonomy_error_logs_user_id", "autonomy_error_logs", ["user_id"])
    op.create_index("ix_autonomy_error_logs_error_type", "autonomy_error_logs", ["error_type"])

    op.create_table(
        "calibration_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=False),
        sa.Column("action", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("applies_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calibration_rules_user_id", "calibration_rules", ["user_id"])
    op.create_index("ix_calibration_rules_rule_type", "calibration_rules", ["rule_type"])


def downgrade() -> None:
    op.drop_index("ix_calibration_rules_rule_type", table_name="calibration_rules")
    op.drop_index("ix_calibration_rules_user_id", table_name="calibration_rules")
    op.drop_table("calibration_rules")
    op.drop_index("ix_autonomy_error_logs_error_type", table_name="autonomy_error_logs")
    op.drop_index("ix_autonomy_error_logs_user_id", table_name="autonomy_error_logs")
    op.drop_table("autonomy_error_logs")
    op.drop_table("autonomy_budgets")
