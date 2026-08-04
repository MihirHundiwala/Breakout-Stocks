"""Add immutable chart evidence for technical analyses.

Revision ID: f7a9c1e3d406
Revises: d4f6a8c0e215
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f7a9c1e3d406"
down_revision: str | Sequence[str] | None = "d4f6a8c0e215"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_snapshots",
        sa.Column("high_26_week", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "analysis_snapshots",
        sa.Column("tightness_pass_count", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_high_26_week_positive",
        "analysis_snapshots",
        "high_26_week IS NULL OR high_26_week > 0",
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_tightness_pass_count",
        "analysis_snapshots",
        "tightness_pass_count IS NULL OR tightness_pass_count BETWEEN 0 AND 4",
    )
    op.create_table(
        "analysis_chart_snapshots",
        sa.Column("analysis_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("resistance_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("resistance_zone_lower", sa.Numeric(18, 4), nullable=False),
        sa.Column("resistance_zone_upper", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "resistance_touch_dates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "candles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "window_start <= window_end",
            name="ck_analysis_chart_snapshots_window",
        ),
        sa.CheckConstraint(
            "resistance_zone_lower > 0 "
            "AND resistance_price >= resistance_zone_lower "
            "AND resistance_zone_upper >= resistance_price",
            name="ck_analysis_chart_snapshots_resistance_zone",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(candles) = 'array' "
            "AND jsonb_array_length(candles) BETWEEN 20 AND 130",
            name="ck_analysis_chart_snapshots_candles",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resistance_touch_dates) = 'array'",
            name="ck_analysis_chart_snapshots_touch_dates",
        ),
        sa.CheckConstraint(
            "schema_version = btrim(schema_version) AND schema_version <> ''",
            name="ck_analysis_chart_snapshots_schema_version",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_snapshot_id"],
            ["analysis_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("analysis_snapshot_id"),
    )


def downgrade() -> None:
    op.drop_table("analysis_chart_snapshots")
    op.drop_constraint(
        "ck_analysis_snapshots_tightness_pass_count",
        "analysis_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_analysis_snapshots_high_26_week_positive",
        "analysis_snapshots",
        type_="check",
    )
    op.drop_column("analysis_snapshots", "tightness_pass_count")
    op.drop_column("analysis_snapshots", "high_26_week")
