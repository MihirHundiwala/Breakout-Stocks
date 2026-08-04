"""Add technical-v2 setup states and explanatory result fields.

Revision ID: e3f5a7b9c201
Revises: d7e9f1a3b205
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e3f5a7b9c201"
down_revision: str | Sequence[str] | None = "d7e9f1a3b205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RESULT_COLUMNS = (
    sa.Column("setup_score", sa.Numeric(6, 2), nullable=True),
    sa.Column("stage2_score", sa.Numeric(9, 6), nullable=True),
    sa.Column("relative_strength_score", sa.Numeric(9, 6), nullable=True),
    sa.Column("base_quality_score", sa.Numeric(9, 6), nullable=True),
    sa.Column("volatility_contraction_score", sa.Numeric(9, 6), nullable=True),
    sa.Column("volume_contraction_score", sa.Numeric(9, 6), nullable=True),
    sa.Column("resistance_quality_score", sa.Numeric(9, 6), nullable=True),
    sa.Column("proximity_score", sa.Numeric(9, 6), nullable=True),
    sa.Column("closing_quality_score", sa.Numeric(9, 6), nullable=True),
    sa.Column("consolidation_window", sa.Integer(), nullable=True),
    sa.Column("consolidation_start", sa.Date(), nullable=True),
    sa.Column("base_high", sa.Numeric(18, 4), nullable=True),
    sa.Column("base_low", sa.Numeric(18, 4), nullable=True),
    sa.Column("base_depth_pct", sa.Numeric(12, 8), nullable=True),
    sa.Column("base_position", sa.Numeric(12, 8), nullable=True),
    sa.Column("resistance_price", sa.Numeric(18, 4), nullable=True),
    sa.Column("resistance_touch_count", sa.Integer(), nullable=True),
    sa.Column("resistance_dispersion_pct", sa.Numeric(12, 8), nullable=True),
    sa.Column("resistance_touch_dates", sa.JSON(), nullable=True),
    sa.Column("distance_to_resistance_pct", sa.Numeric(12, 8), nullable=True),
    sa.Column("atr14", sa.Numeric(18, 8), nullable=True),
    sa.Column("atr_pct", sa.Numeric(12, 8), nullable=True),
    sa.Column("atr_contraction_ratio", sa.Numeric(12, 8), nullable=True),
    sa.Column("return_volatility_ratio", sa.Numeric(12, 8), nullable=True),
    sa.Column("daily_range_ratio", sa.Numeric(12, 8), nullable=True),
    sa.Column("ma_spread", sa.Numeric(12, 8), nullable=True),
    sa.Column("volume_dryup_ratio", sa.Numeric(12, 8), nullable=True),
    sa.Column("breakout_volume_ratio", sa.Numeric(12, 8), nullable=True),
    sa.Column("distribution_day_count", sa.Integer(), nullable=True),
    sa.Column("close_location_value", sa.Numeric(12, 8), nullable=True),
    sa.Column("breakout_extension_atr", sa.Numeric(12, 8), nullable=True),
    sa.Column("average_traded_value_20", sa.Numeric(24, 4), nullable=True),
    sa.Column("rejection_reasons", sa.JSON(), nullable=True),
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
        "technical_status IN ("
        "'NO_SETUP', 'FORMING', 'READY', 'BREAKOUT', 'WEAK_BREAKOUT', "
        "'FAILED_BREAKOUT', 'SETUP_FOUND')",
    )
    for column in RESULT_COLUMNS:
        op.add_column("analysis_snapshots", column)
    op.create_check_constraint(
        "ck_analysis_snapshots_setup_score_range",
        "analysis_snapshots",
        "setup_score IS NULL OR (setup_score >= 0 AND setup_score <= 100)",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_stage2_score_range",
        "analysis_snapshots",
        "stage2_score IS NULL OR (stage2_score >= 0 AND stage2_score <= 1)",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_rs_score_range",
        "analysis_snapshots",
        "relative_strength_score IS NULL OR "
        "(relative_strength_score >= 0 AND relative_strength_score <= 1)",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE analysis_snapshots SET technical_status = 'NO_SETUP' "
        "WHERE technical_status IN ("
        "'FORMING', 'READY', 'BREAKOUT', 'WEAK_BREAKOUT', 'FAILED_BREAKOUT')"
    )
    for name in (
        "ck_analysis_snapshots_rs_score_range",
        "ck_analysis_snapshots_stage2_score_range",
        "ck_analysis_snapshots_setup_score_range",
    ):
        op.drop_constraint(name, "analysis_snapshots", type_="check")
    for column in reversed(RESULT_COLUMNS):
        op.drop_column("analysis_snapshots", column.name)
    op.drop_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_technical_status",
        "analysis_snapshots",
        "technical_status IN ('NO_SETUP', 'SETUP_FOUND')",
    )
