"""Add watchlist-added setup alert state.

Revision ID: f5b7d9a1c324
Revises: e4a6c8f0b217
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f5b7d9a1c324"
down_revision: str | Sequence[str] | None = "e4a6c8f0b217"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_watchlist_items",
        sa.Column(
            "telegram_setup_alert_pending",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.drop_constraint(
        "ck_telegram_notification_event_kind",
        "telegram_notification_outbox",
        type_="check",
    )
    op.create_check_constraint(
        "ck_telegram_notification_event_kind",
        "telegram_notification_outbox",
        "event_kind IN ('STATUS_CHANGED', 'SETUP_STRUCTURE_CHANGED', 'WATCHLIST_ADDED')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_telegram_notification_event_kind",
        "telegram_notification_outbox",
        type_="check",
    )
    op.create_check_constraint(
        "ck_telegram_notification_event_kind",
        "telegram_notification_outbox",
        "event_kind IN ('STATUS_CHANGED', 'SETUP_STRUCTURE_CHANGED')",
    )
    op.drop_column(
        "user_watchlist_items",
        "telegram_setup_alert_pending",
    )
