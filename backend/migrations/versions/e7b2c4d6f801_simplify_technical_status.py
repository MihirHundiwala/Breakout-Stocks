"""Simplify technical analysis to a binary setup status.

Revision ID: e7b2c4d6f801
Revises: d2c4e6f8a105
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "e7b2c4d6f801"
down_revision: str | Sequence[str] | None = "d2c4e6f8a105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_analysis_snapshots_status_fields",
        "analysis_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        type_="check",
    )
    op.execute(
        "UPDATE analysis_snapshots "
        "SET technical_status = 'SETUP_FOUND', "
        "pivot_price = NULL, breakout_confirmed_on = NULL "
        "WHERE technical_status IN ('ABOUT_TO_BREAKOUT', 'BREAKOUT_CONFIRMED')"
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        "technical_status IN ('NO_SETUP', 'SETUP_FOUND')",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_status_fields",
        "analysis_snapshots",
        "pivot_price IS NULL AND breakout_confirmed_on IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_analysis_snapshots_status_fields",
        "analysis_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        type_="check",
    )
    op.execute(
        "UPDATE analysis_snapshots SET technical_status = 'NO_SETUP' "
        "WHERE technical_status = 'SETUP_FOUND'"
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        "technical_status IN "
        "('NO_SETUP', 'ABOUT_TO_BREAKOUT', 'BREAKOUT_CONFIRMED')",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_status_fields",
        "analysis_snapshots",
        "(technical_status = 'NO_SETUP' AND pivot_price IS NULL "
        "AND breakout_confirmed_on IS NULL) OR "
        "(technical_status = 'ABOUT_TO_BREAKOUT' AND pivot_price IS NOT NULL "
        "AND breakout_confirmed_on IS NULL) OR "
        "(technical_status = 'BREAKOUT_CONFIRMED' AND pivot_price IS NOT NULL "
        "AND breakout_confirmed_on IS NOT NULL)",
    )
