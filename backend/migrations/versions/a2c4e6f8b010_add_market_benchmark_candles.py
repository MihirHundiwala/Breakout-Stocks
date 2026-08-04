"""Add market benchmark candle history.

Revision ID: a2c4e6f8b010
Revises: e7b2c4d6f801
Create Date: 2026-07-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a2c4e6f8b010"
down_revision: str | Sequence[str] | None = "e7b2c4d6f801"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_benchmarks",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("instrument_key", sa.String(length=128), nullable=False),
        sa.Column(
            "source_fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "code = upper(btrim(code)) AND code <> ''",
            name="ck_market_benchmarks_code",
        ),
        sa.CheckConstraint(
            "name = btrim(name) AND name <> ''",
            name="ck_market_benchmarks_name",
        ),
        sa.CheckConstraint(
            "provider = upper(btrim(provider)) AND provider <> ''",
            name="ck_market_benchmarks_provider",
        ),
        sa.CheckConstraint(
            "instrument_key = btrim(instrument_key) AND instrument_key <> ''",
            name="ck_market_benchmarks_instrument_key",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_market_benchmarks_code"),
        sa.UniqueConstraint(
            "provider",
            "instrument_key",
            name="uq_market_benchmarks_provider_key",
        ),
    )
    op.create_table(
        "benchmark_daily_candles",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("benchmark_id", sa.Integer(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("high_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("low_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("close_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("open_interest", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "source_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "open_price > 0 AND high_price > 0 AND "
                "low_price > 0 AND close_price > 0"
            ),
            name="ck_benchmark_daily_candles_prices_positive",
        ),
        sa.CheckConstraint(
            "high_price >= greatest(open_price, low_price, close_price)",
            name="ck_benchmark_daily_candles_high",
        ),
        sa.CheckConstraint(
            "low_price <= least(open_price, high_price, close_price)",
            name="ck_benchmark_daily_candles_low",
        ),
        sa.CheckConstraint(
            "volume >= 0 AND open_interest >= 0",
            name="ck_benchmark_daily_candles_activity",
        ),
        sa.CheckConstraint(
            "source = upper(btrim(source)) AND source <> ''",
            name="ck_benchmark_daily_candles_source",
        ),
        sa.ForeignKeyConstraint(
            ["benchmark_id"],
            ["market_benchmarks.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "benchmark_id",
            "trading_date",
            name="uq_benchmark_daily_candles_benchmark_date",
        ),
    )


def downgrade() -> None:
    op.drop_table("benchmark_daily_candles")
    op.drop_table("market_benchmarks")
