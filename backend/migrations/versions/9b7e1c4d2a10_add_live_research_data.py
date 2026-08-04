"""Add retained live research data.

Revision ID: 9b7e1c4d2a10
Revises: 60c5d892abfe
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9b7e1c4d2a10"
down_revision: str | Sequence[str] | None = "60c5d892abfe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_instrument_identities",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("instrument_key", sa.String(128), nullable=False),
        sa.Column("isin", sa.String(12), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider = upper(btrim(provider)) AND provider <> ''", name="ck_provider_identities_provider"),
        sa.CheckConstraint("instrument_key = btrim(instrument_key) AND instrument_key <> ''", name="ck_provider_identities_key"),
        sa.CheckConstraint("isin = upper(btrim(isin)) AND isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'", name="ck_provider_identities_isin"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_provider_identities_dates"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_instrument_identities_instrument_id", "provider_instrument_identities", ["instrument_id"])
    op.create_index("uq_provider_identities_active_instrument", "provider_instrument_identities", ["instrument_id", "provider"], unique=True, postgresql_where=sa.text("effective_to IS NULL"))
    op.create_index("uq_provider_identities_active_key", "provider_instrument_identities", ["provider", "instrument_key"], unique=True, postgresql_where=sa.text("effective_to IS NULL"))

    op.create_table(
        "daily_candles",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("high_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("low_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("close_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("open_interest", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0", name="ck_daily_candles_prices_positive"),
        sa.CheckConstraint("high_price >= greatest(open_price, low_price, close_price)", name="ck_daily_candles_high"),
        sa.CheckConstraint("low_price <= least(open_price, high_price, close_price)", name="ck_daily_candles_low"),
        sa.CheckConstraint("volume >= 0 AND open_interest >= 0", name="ck_daily_candles_activity_non_negative"),
        sa.CheckConstraint("source = upper(btrim(source)) AND source <> ''", name="ck_daily_candles_source"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id", "trading_date", name="uq_daily_candles_instrument_date"),
    )

    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_key", sa.String(128), nullable=False),
        sa.Column("action_type", sa.Enum("SPLIT", "BONUS", "DIVIDEND", "RIGHTS", "OTHER", name="ck_corporate_actions_type", native_enum=False, create_constraint=True, length=16), nullable=False),
        sa.Column("announcement_date", sa.Date(), nullable=True),
        sa.Column("ex_date", sa.Date(), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("ratio", sa.String(32), nullable=True),
        sa.Column("old_isin", sa.String(12), nullable=True),
        sa.Column("new_isin", sa.String(12), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider = upper(btrim(provider)) AND provider <> ''", name="ck_corporate_actions_provider"),
        sa.CheckConstraint("provider_event_key = btrim(provider_event_key) AND provider_event_key <> ''", name="ck_corporate_actions_event_key"),
        sa.CheckConstraint("ratio IS NULL OR ratio = btrim(ratio)", name="ck_corporate_actions_ratio"),
        sa.CheckConstraint("old_isin IS NULL OR old_isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'", name="ck_corporate_actions_old_isin"),
        sa.CheckConstraint("new_isin IS NULL OR new_isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'", name="ck_corporate_actions_new_isin"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_event_key", name="uq_corporate_actions_provider_event"),
    )
    op.create_index("ix_corporate_actions_instrument_id", "corporate_actions", ["instrument_id"])

    op.create_table(
        "fundamental_snapshots",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("coverage", sa.Enum("UNKNOWN", "PARTIAL", "COMPLETE", name="ck_fundamental_snapshots_coverage", native_enum=False, create_constraint=True, length=16), nullable=False),
        sa.Column("available_metric_count", sa.Integer(), nullable=False),
        sa.Column("expected_metric_count", sa.Integer(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.CheckConstraint("available_metric_count >= 0 AND expected_metric_count > 0 AND available_metric_count <= expected_metric_count", name="ck_fundamental_snapshots_counts"),
        sa.CheckConstraint("schema_version = btrim(schema_version) AND schema_version <> ''", name="ck_fundamental_snapshots_version"),
        sa.CheckConstraint("source = upper(btrim(source)) AND source <> ''", name="ck_fundamental_snapshots_source"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id", "as_of_date", "schema_version", name="uq_fundamental_snapshots_identity"),
    )
    op.create_index("ix_fundamental_snapshots_instrument_id", "fundamental_snapshots", ["instrument_id"])

    op.create_table(
        "fundamental_periods",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("period_kind", sa.Enum("YEARLY", "QUARTERLY", name="ck_fundamental_periods_kind", native_enum=False, create_constraint=True, length=16), nullable=False),
        sa.Column("statement_basis", sa.Enum("CONSOLIDATED", "STANDALONE", name="ck_fundamental_periods_basis", native_enum=False, create_constraint=True, length=16), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.CheckConstraint("currency = upper(btrim(currency)) AND currency <> ''", name="ck_fundamental_periods_currency"),
        sa.CheckConstraint("source = upper(btrim(source)) AND source <> ''", name="ck_fundamental_periods_source"),
        sa.CheckConstraint("schema_version = btrim(schema_version) AND schema_version <> ''", name="ck_fundamental_periods_version"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "period_end", "period_kind", "statement_basis", "schema_version", name="uq_fundamental_periods_identity"),
    )
    op.create_index("ix_fundamental_periods_company_id", "fundamental_periods", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_fundamental_periods_company_id", table_name="fundamental_periods")
    op.drop_table("fundamental_periods")
    op.drop_index("ix_fundamental_snapshots_instrument_id", table_name="fundamental_snapshots")
    op.drop_table("fundamental_snapshots")
    op.drop_index("ix_corporate_actions_instrument_id", table_name="corporate_actions")
    op.drop_table("corporate_actions")
    op.drop_table("daily_candles")
    op.drop_index("uq_provider_identities_active_key", table_name="provider_instrument_identities", postgresql_where=sa.text("effective_to IS NULL"))
    op.drop_index("uq_provider_identities_active_instrument", table_name="provider_instrument_identities", postgresql_where=sa.text("effective_to IS NULL"))
    op.drop_index("ix_provider_instrument_identities_instrument_id", table_name="provider_instrument_identities")
    op.drop_table("provider_instrument_identities")
