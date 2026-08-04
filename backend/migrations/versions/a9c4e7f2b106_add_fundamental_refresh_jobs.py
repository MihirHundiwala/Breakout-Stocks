"""Add dedicated fundamental refresh jobs.

Revision ID: a9c4e7f2b106
Revises: e3f5a7b9c201
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op


revision: str = "a9c4e7f2b106"
down_revision: str | Sequence[str] | None = "e3f5a7b9c201"
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
        "job_type IN ("
        "'ONBOARD_INSTRUMENT', "
        "'ANALYZE_INSTRUMENT', "
        "'REFRESH_FUNDAMENTALS'"
        ")",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE analysis_jobs SET job_type = 'ANALYZE_INSTRUMENT' "
        "WHERE job_type = 'REFRESH_FUNDAMENTALS'"
    )
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
