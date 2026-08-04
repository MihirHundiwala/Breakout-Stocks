"""Store compact terminal technical data state.

Revision ID: c1e3f5a7d902
Revises: b4d6f8a0c213
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c1e3f5a7d902"
down_revision: str | Sequence[str] | None = "b4d6f8a0c213"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracked_instruments",
        sa.Column("terminal_data_error_session", sa.Date(), nullable=True),
    )
    op.add_column(
        "tracked_instruments",
        sa.Column("terminal_data_error_code", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_tracked_instruments_terminal_data_error_pair",
        "tracked_instruments",
        "(terminal_data_error_session IS NULL AND terminal_data_error_code IS NULL) "
        "OR (terminal_data_error_session IS NOT NULL "
        "AND terminal_data_error_code IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_tracked_instruments_terminal_data_error_code",
        "tracked_instruments",
        "terminal_data_error_code IS NULL "
        "OR (terminal_data_error_code = upper(btrim(terminal_data_error_code)) "
        "AND terminal_data_error_code <> '')",
    )
    op.execute(
        """
        WITH latest AS (
            SELECT DISTINCT ON (tracked_instrument_id)
                   tracked_instrument_id, target_session, status, error_code
            FROM analysis_jobs
            WHERE job_type = 'ANALYZE_INSTRUMENT'
              AND status IN ('SUCCEEDED', 'FAILED')
            ORDER BY tracked_instrument_id, completed_at DESC, id DESC
        )
        UPDATE tracked_instruments AS tracking
        SET terminal_data_error_session = latest.target_session,
            terminal_data_error_code = latest.error_code
        FROM latest
        WHERE latest.tracked_instrument_id = tracking.id
          AND latest.status = 'FAILED'
          AND latest.error_code IN (
              'INSUFFICIENT_LISTING_HISTORY',
              'PERSISTENT_CANDLE_GAPS'
          )
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tracked_instruments_terminal_data_error_code",
        "tracked_instruments",
        type_="check",
    )
    op.drop_constraint(
        "ck_tracked_instruments_terminal_data_error_pair",
        "tracked_instruments",
        type_="check",
    )
    op.drop_column("tracked_instruments", "terminal_data_error_code")
    op.drop_column("tracked_instruments", "terminal_data_error_session")
