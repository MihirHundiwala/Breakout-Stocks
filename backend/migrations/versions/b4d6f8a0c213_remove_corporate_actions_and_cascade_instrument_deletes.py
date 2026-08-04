"""Remove corporate actions and cascade instrument-owned data.

Revision ID: b4d6f8a0c213
Revises: a9c4e7f2b106
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b4d6f8a0c213"
down_revision: str | Sequence[str] | None = "a9c4e7f2b106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INSTRUMENT_FOREIGN_KEYS = (
    ("analysis_snapshots", "analysis_snapshots_instrument_id_fkey", "instrument_id"),
    ("tracked_instruments", "tracked_instruments_instrument_id_fkey", "instrument_id"),
    ("user_watchlist_items", "user_watchlist_items_instrument_id_fkey", "instrument_id"),
    (
        "provider_instrument_identities",
        "provider_instrument_identities_instrument_id_fkey",
        "instrument_id",
    ),
    ("daily_candles", "daily_candles_instrument_id_fkey", "instrument_id"),
    (
        "fundamental_snapshots",
        "fundamental_snapshots_instrument_id_fkey",
        "instrument_id",
    ),
)


def _replace_foreign_key(
    table_name: str,
    constraint_name: str,
    local_column: str,
    referred_table: str,
    referred_column: str,
    *,
    ondelete: str,
) -> None:
    op.drop_constraint(constraint_name, table_name, type_="foreignkey")
    op.create_foreign_key(
        constraint_name,
        table_name,
        referred_table,
        [local_column],
        [referred_column],
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.drop_table("corporate_actions")
    for table_name, constraint_name, local_column in INSTRUMENT_FOREIGN_KEYS:
        _replace_foreign_key(
            table_name,
            constraint_name,
            local_column,
            "instruments",
            "id",
            ondelete="CASCADE",
        )
    _replace_foreign_key(
        "fundamental_periods",
        "fundamental_periods_company_id_fkey",
        "company_id",
        "companies",
        "id",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    _replace_foreign_key(
        "fundamental_periods",
        "fundamental_periods_company_id_fkey",
        "company_id",
        "companies",
        "id",
        ondelete="RESTRICT",
    )
    for table_name, constraint_name, local_column in INSTRUMENT_FOREIGN_KEYS:
        _replace_foreign_key(
            table_name,
            constraint_name,
            local_column,
            "instruments",
            "id",
            ondelete="RESTRICT",
        )

    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_key", sa.String(128), nullable=False),
        sa.Column(
            "action_type",
            sa.Enum(
                "SPLIT",
                "BONUS",
                "DIVIDEND",
                "RIGHTS",
                "OTHER",
                name="ck_corporate_actions_type",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("announcement_date", sa.Date(), nullable=True),
        sa.Column("ex_date", sa.Date(), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("ratio", sa.String(32), nullable=True),
        sa.Column("old_isin", sa.String(12), nullable=True),
        sa.Column("new_isin", sa.String(12), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider = upper(btrim(provider)) AND provider <> ''",
            name="ck_corporate_actions_provider",
        ),
        sa.CheckConstraint(
            "provider_event_key = btrim(provider_event_key) AND provider_event_key <> ''",
            name="ck_corporate_actions_event_key",
        ),
        sa.CheckConstraint(
            "ratio IS NULL OR ratio = btrim(ratio)",
            name="ck_corporate_actions_ratio",
        ),
        sa.CheckConstraint(
            "old_isin IS NULL OR old_isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'",
            name="ck_corporate_actions_old_isin",
        ),
        sa.CheckConstraint(
            "new_isin IS NULL OR new_isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'",
            name="ck_corporate_actions_new_isin",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_event_key",
            name="uq_corporate_actions_provider_event",
        ),
    )
    op.create_index(
        "ix_corporate_actions_instrument_id",
        "corporate_actions",
        ["instrument_id"],
    )
