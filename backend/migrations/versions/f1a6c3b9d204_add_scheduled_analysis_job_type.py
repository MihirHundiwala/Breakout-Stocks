"""Add scheduled analysis job type.

Revision ID: f1a6c3b9d204
Revises: c4d2e8a7f901
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "f1a6c3b9d204"
down_revision: str | Sequence[str] | None = "c4d2e8a7f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_analysis_jobs_job_type",
        "analysis_jobs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_analysis_jobs_job_type",
        "analysis_jobs",
        "job_type IN ('ONBOARD_INSTRUMENT', 'ANALYZE_INSTRUMENT')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE analysis_jobs SET job_type = 'ONBOARD_INSTRUMENT' "
        "WHERE job_type = 'ANALYZE_INSTRUMENT'"
    )
    op.drop_constraint(
        "ck_analysis_jobs_job_type",
        "analysis_jobs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_analysis_jobs_job_type",
        "analysis_jobs",
        "job_type = 'ONBOARD_INSTRUMENT'",
    )
