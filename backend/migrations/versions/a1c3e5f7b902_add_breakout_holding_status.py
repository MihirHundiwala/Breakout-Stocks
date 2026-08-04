"""Add breakout-holding technical status.

Revision ID: a1c3e5f7b902
Revises: f8b0d2e4a607
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op


revision: str = "a1c3e5f7b902"
down_revision: str | Sequence[str] | None = "f8b0d2e4a607"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


V9_STATUSES = (
    "'NO_SETUP', 'CONSOLIDATING', 'BREAKOUT', 'EARLY_RECOVERY_BREAKOUT', "
    "'WEAK_BREAKOUT', 'BREAKOUT_HOLDING', 'RETEST', 'FORMING', 'READY', "
    "'FAILED_BREAKOUT', 'SETUP_FOUND'"
)
V8_STATUSES = (
    "'NO_SETUP', 'CONSOLIDATING', 'BREAKOUT', 'EARLY_RECOVERY_BREAKOUT', "
    "'WEAK_BREAKOUT', 'RETEST', 'FORMING', 'READY', 'FAILED_BREAKOUT', "
    "'SETUP_FOUND'"
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
        f"technical_status IN ({V9_STATUSES})",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE analysis_snapshots SET technical_status = 'NO_SETUP' "
        "WHERE technical_status = 'BREAKOUT_HOLDING'"
    )
    op.drop_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        f"technical_status IN ({V8_STATUSES})",
    )
