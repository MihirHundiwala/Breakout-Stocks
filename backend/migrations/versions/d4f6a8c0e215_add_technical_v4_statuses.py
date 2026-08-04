"""Add technical-v4 consolidation and retest statuses.

Revision ID: d4f6a8c0e215
Revises: c1e3f5a7d902
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op


revision: str = "d4f6a8c0e215"
down_revision: str | Sequence[str] | None = "c1e3f5a7d902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ALL_STATUSES = (
    "'NO_SETUP', 'CONSOLIDATING', 'BREAKOUT', 'WEAK_BREAKOUT', 'RETEST', "
    "'FORMING', 'READY', 'FAILED_BREAKOUT', 'SETUP_FOUND'"
)
V3_STATUSES = (
    "'NO_SETUP', 'FORMING', 'READY', 'BREAKOUT', 'WEAK_BREAKOUT', "
    "'FAILED_BREAKOUT', 'SETUP_FOUND'"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        f"technical_status IN ({ALL_STATUSES})",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE analysis_snapshots SET technical_status = 'NO_SETUP' "
        "WHERE technical_status IN ('CONSOLIDATING', 'RETEST')"
    )
    op.drop_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        f"technical_status IN ({V3_STATUSES})",
    )
