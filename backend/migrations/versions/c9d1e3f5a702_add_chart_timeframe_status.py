"""Store the independently evaluated status for each chart timeframe.

Revision ID: c9d1e3f5a702
Revises: a8c1e4f7b902
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c9d1e3f5a702"
down_revision: str | Sequence[str] | None = "a8c1e4f7b902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_chart_snapshots",
        sa.Column("technical_status", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_analysis_chart_snapshots_technical_status",
        "analysis_chart_snapshots",
        "technical_status IS NULL OR technical_status IN ("
        "'NO_SETUP', 'FORMING', 'READY', 'BREAKOUT', 'RETEST', "
        "'FAILED_BREAKOUT', 'SETUP_FOUND', 'CONSOLIDATING', "
        "'WEAK_BREAKOUT', 'EARLY_RECOVERY_BREAKOUT', "
        "'BREAKOUT_HOLDING')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_analysis_chart_snapshots_technical_status",
        "analysis_chart_snapshots",
        type_="check",
    )
    op.drop_column("analysis_chart_snapshots", "technical_status")
