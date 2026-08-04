"""Add durable analysis-job retry scheduling.

Revision ID: c4d2e8a7f901
Revises: 9b7e1c4d2a10
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c4d2e8a7f901"
down_revision: str | Sequence[str] | None = "9b7e1c4d2a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_jobs",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.execute("UPDATE analysis_jobs SET next_attempt_at = created_at")
    op.alter_column("analysis_jobs", "next_attempt_at", nullable=False)
    op.create_check_constraint(
        "ck_analysis_jobs_next_attempt_at",
        "analysis_jobs",
        "next_attempt_at >= created_at",
    )
    op.create_index(
        "ix_analysis_jobs_pending_schedule",
        "analysis_jobs",
        ["status", "next_attempt_at", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_jobs_pending_schedule",
        table_name="analysis_jobs",
    )
    op.drop_constraint(
        "ck_analysis_jobs_next_attempt_at",
        "analysis_jobs",
        type_="check",
    )
    op.drop_column("analysis_jobs", "next_attempt_at")
