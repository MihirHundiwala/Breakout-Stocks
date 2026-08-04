"""Add multi-timeframe technical chart evidence.

Revision ID: b2d4f6a8c013
Revises: a1c3e5f7b902
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b2d4f6a8c013"
down_revision: str | Sequence[str] | None = "a1c3e5f7b902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_snapshots",
        sa.Column("consolidation_timeframe", sa.String(16), nullable=True),
    )
    op.execute(
        "UPDATE analysis_snapshots SET consolidation_timeframe = 'DAILY' "
        "WHERE consolidation_window IS NOT NULL"
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_consolidation_timeframe",
        "analysis_snapshots",
        "consolidation_timeframe IS NULL "
        "OR consolidation_timeframe IN ('DAILY', 'WEEKLY')",
    )

    op.drop_constraint(
        "analysis_chart_snapshots_pkey",
        "analysis_chart_snapshots",
        type_="primary",
    )
    op.add_column(
        "analysis_chart_snapshots",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
    )
    op.add_column(
        "analysis_chart_snapshots",
        sa.Column(
            "timeframe",
            sa.String(16),
            nullable=False,
            server_default="DAILY",
        ),
    )
    op.add_column(
        "analysis_chart_snapshots",
        sa.Column("period_count", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE analysis_chart_snapshots AS chart "
        "SET period_count = COALESCE(snapshot.consolidation_window, "
        "GREATEST(20, jsonb_array_length(chart.candles) - 1)), "
        "timeframe = COALESCE(snapshot.consolidation_timeframe, 'DAILY') "
        "FROM analysis_snapshots AS snapshot "
        "WHERE snapshot.id = chart.analysis_snapshot_id"
    )
    op.alter_column(
        "analysis_chart_snapshots",
        "period_count",
        nullable=False,
    )
    op.alter_column(
        "analysis_chart_snapshots",
        "timeframe",
        server_default=None,
    )
    op.create_primary_key(
        "pk_analysis_chart_snapshots",
        "analysis_chart_snapshots",
        ["id"],
    )
    op.create_unique_constraint(
        "uq_analysis_chart_snapshots_analysis_timeframe",
        "analysis_chart_snapshots",
        ["analysis_snapshot_id", "timeframe"],
    )
    op.create_check_constraint(
        "ck_analysis_chart_snapshots_timeframe_period",
        "analysis_chart_snapshots",
        "(timeframe = 'DAILY' AND period_count BETWEEN 20 AND 120) OR "
        "(timeframe = 'WEEKLY' AND period_count BETWEEN 26 AND 104)",
    )
    op.create_index(
        "ix_analysis_chart_snapshots_analysis_snapshot_id",
        "analysis_chart_snapshots",
        ["analysis_snapshot_id"],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM analysis_chart_snapshots WHERE timeframe <> 'DAILY'"
    )
    op.drop_index(
        "ix_analysis_chart_snapshots_analysis_snapshot_id",
        table_name="analysis_chart_snapshots",
    )
    op.drop_constraint(
        "ck_analysis_chart_snapshots_timeframe_period",
        "analysis_chart_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "uq_analysis_chart_snapshots_analysis_timeframe",
        "analysis_chart_snapshots",
        type_="unique",
    )
    op.drop_constraint(
        "pk_analysis_chart_snapshots",
        "analysis_chart_snapshots",
        type_="primary",
    )
    op.drop_column("analysis_chart_snapshots", "period_count")
    op.drop_column("analysis_chart_snapshots", "timeframe")
    op.drop_column("analysis_chart_snapshots", "id")
    op.create_primary_key(
        "analysis_chart_snapshots_pkey",
        "analysis_chart_snapshots",
        ["analysis_snapshot_id"],
    )
    op.drop_constraint(
        "ck_analysis_snapshots_consolidation_timeframe",
        "analysis_snapshots",
        type_="check",
    )
    op.drop_column("analysis_snapshots", "consolidation_timeframe")
