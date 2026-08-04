"""Add the fixture analysis domain model.

Revision ID: 20260723_0002
Revises: 20260721_0001
Create Date: 2026-07-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_0002"
down_revision: str | Sequence[str] | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "name = btrim(name) AND name <> ''",
            name="ck_companies_name_normalized",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "instruments",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column(
            "trading_symbol",
            sa.String(length=64),
            nullable=False,
        ),
        sa.CheckConstraint(
            "exchange = btrim(exchange) "
            "AND exchange = upper(exchange) "
            "AND exchange <> ''",
            name="ck_instruments_exchange_normalized",
        ),
        sa.CheckConstraint(
            "trading_symbol = btrim(trading_symbol) "
            "AND trading_symbol = upper(trading_symbol) "
            "AND trading_symbol <> ''",
            name="ck_instruments_symbol_normalized",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange",
            "trading_symbol",
            name="uq_instruments_exchange_trading_symbol",
        ),
    )
    op.create_index(
        op.f("ix_instruments_company_id"),
        "instruments",
        ["company_id"],
        unique=False,
    )
    op.create_table(
        "analysis_snapshots",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("analysis_date", sa.Date(), nullable=False),
        sa.Column(
            "technical_status",
            sa.Enum(
                "NO_SETUP",
                "ABOUT_TO_BREAKOUT",
                "BREAKOUT_CONFIRMED",
                name="ck_analysis_snapshots_technical_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "fundamental_coverage",
            sa.Enum(
                "UNKNOWN",
                "PARTIAL",
                "COMPLETE",
                name="ck_analysis_snapshots_fundamental_coverage",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "close_price",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
        ),
        sa.Column(
            "previous_close_price",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
        ),
        sa.Column(
            "pivot_price",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
        ),
        sa.Column("breakout_confirmed_on", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "source_fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "algorithm_version",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "candle_revision",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(technical_status = 'NO_SETUP' "
            "AND pivot_price IS NULL "
            "AND breakout_confirmed_on IS NULL) "
            "OR (technical_status = 'ABOUT_TO_BREAKOUT' "
            "AND pivot_price IS NOT NULL "
            "AND breakout_confirmed_on IS NULL) "
            "OR (technical_status = 'BREAKOUT_CONFIRMED' "
            "AND pivot_price IS NOT NULL "
            "AND breakout_confirmed_on IS NOT NULL)",
            name="ck_analysis_snapshots_status_fields",
        ),
        sa.CheckConstraint(
            "algorithm_version = btrim(algorithm_version) "
            "AND algorithm_version <> ''",
            name="ck_analysis_snapshots_algorithm_version",
        ),
        sa.CheckConstraint(
            "candle_revision = btrim(candle_revision) "
            "AND candle_revision <> ''",
            name="ck_analysis_snapshots_candle_revision",
        ),
        sa.CheckConstraint(
            "source = btrim(source) "
            "AND source = upper(source) "
            "AND source <> ''",
            name="ck_analysis_snapshots_source_normalized",
        ),
        sa.CheckConstraint(
            "breakout_confirmed_on IS NULL "
            "OR breakout_confirmed_on <= analysis_date",
            name="ck_analysis_snapshots_confirmation_date",
        ),
        sa.CheckConstraint(
            "close_price > 0",
            name="ck_analysis_snapshots_close_positive",
        ),
        sa.CheckConstraint(
            "pivot_price IS NULL OR pivot_price > 0",
            name="ck_analysis_snapshots_pivot_positive",
        ),
        sa.CheckConstraint(
            "previous_close_price > 0",
            name="ck_analysis_snapshots_previous_close_positive",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "analysis_date",
            "algorithm_version",
            "candle_revision",
            name=(
                "uq_analysis_snapshots_"
                "instrument_date_version_revision"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_table("analysis_snapshots")
    op.drop_index(
        op.f("ix_instruments_company_id"),
        table_name="instruments",
    )
    op.drop_table("instruments")
    op.drop_table("companies")
