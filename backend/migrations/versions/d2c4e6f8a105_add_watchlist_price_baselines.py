"""Persist the price baseline for each watchlist activation.

Revision ID: d2c4e6f8a105
Revises: b8e9f0a1c234
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d2c4e6f8a105"
down_revision: str | Sequence[str] | None = "b8e9f0a1c234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_watchlist_items",
        sa.Column("baseline_session", sa.Date(), nullable=True),
    )
    op.add_column(
        "user_watchlist_items",
        sa.Column(
            "baseline_close_price",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
        ),
    )

    # Existing memberships predate this field. Anchor them to the newest retained
    # market close at or before their latest activation; fall back to the shared
    # tracking target only when no historical research is retained yet.
    op.execute(
        """
        UPDATE user_watchlist_items AS membership
        SET baseline_session = COALESCE(
            (
                SELECT max(candle.trading_date)
                FROM daily_candles AS candle
                WHERE candle.instrument_id = membership.instrument_id
                  AND candle.trading_date <= (
                      COALESCE(membership.reactivated_at, membership.created_at)
                      AT TIME ZONE 'Asia/Kolkata'
                  )::date
            ),
            (
                SELECT max(snapshot.analysis_date)
                FROM analysis_snapshots AS snapshot
                WHERE snapshot.instrument_id = membership.instrument_id
                  AND snapshot.analysis_date <= (
                      COALESCE(membership.reactivated_at, membership.created_at)
                      AT TIME ZONE 'Asia/Kolkata'
                  )::date
            ),
            (
                SELECT tracking.target_session
                FROM tracked_instruments AS tracking
                WHERE tracking.instrument_id = membership.instrument_id
            ),
            (
                COALESCE(membership.reactivated_at, membership.created_at)
                AT TIME ZONE 'Asia/Kolkata'
            )::date
        )
        """
    )
    op.execute(
        """
        UPDATE user_watchlist_items AS membership
        SET baseline_close_price = COALESCE(
            (
                SELECT candle.close_price
                FROM daily_candles AS candle
                WHERE candle.instrument_id = membership.instrument_id
                  AND candle.trading_date = membership.baseline_session
                LIMIT 1
            ),
            (
                SELECT snapshot.close_price
                FROM analysis_snapshots AS snapshot
                WHERE snapshot.instrument_id = membership.instrument_id
                  AND snapshot.analysis_date = membership.baseline_session
                ORDER BY snapshot.generated_at DESC, snapshot.id DESC
                LIMIT 1
            )
        )
        """
    )
    op.alter_column(
        "user_watchlist_items",
        "baseline_session",
        existing_type=sa.Date(),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_user_watchlist_items_baseline_close_positive",
        "user_watchlist_items",
        "baseline_close_price IS NULL OR baseline_close_price > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_watchlist_items_baseline_close_positive",
        "user_watchlist_items",
        type_="check",
    )
    op.drop_column("user_watchlist_items", "baseline_close_price")
    op.drop_column("user_watchlist_items", "baseline_session")
