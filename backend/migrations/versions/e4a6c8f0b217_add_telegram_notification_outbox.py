"""Add durable Telegram notification outbox.

Revision ID: e4a6c8f0b217
Revises: b2d4f6a8c013
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e4a6c8f0b217"
down_revision: str | Sequence[str] | None = "b2d4f6a8c013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_connections",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=32), nullable=True),
        sa.Column("telegram_username", sa.String(length=32), nullable=True),
        sa.Column("link_token_digest", sa.String(length=64), nullable=True),
        sa.Column("link_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "telegram_username IS NULL OR (telegram_username = lower(btrim(telegram_username)) AND telegram_username <> '')",
            name="ck_telegram_connections_username",
        ),
        sa.CheckConstraint(
            "link_token_digest IS NULL OR link_token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_telegram_connections_token_digest",
        ),
        sa.CheckConstraint(
            "(telegram_chat_id IS NULL AND connected_at IS NULL AND link_token_digest IS NOT NULL AND link_expires_at IS NOT NULL) "
            "OR (telegram_chat_id IS NOT NULL AND connected_at IS NOT NULL AND link_token_digest IS NULL AND link_expires_at IS NULL)",
            name="ck_telegram_connections_state",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("link_token_digest"),
        sa.UniqueConstraint("telegram_chat_id"),
    )
    op.create_table(
        "telegram_bot_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("next_update_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_telegram_bot_state_singleton"),
        sa.CheckConstraint("next_update_id >= 0", name="ck_telegram_bot_state_update_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "telegram_notification_outbox",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("analysis_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("previous_analysis_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("event_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "FAILED",
                name="ck_telegram_notification_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_telegram_notification_attempt_count",
        ),
        sa.CheckConstraint(
            "next_attempt_at >= created_at",
            name="ck_telegram_notification_next_attempt",
        ),
        sa.CheckConstraint(
            "event_kind IN ('STATUS_CHANGED', 'SETUP_STRUCTURE_CHANGED')",
            name="ck_telegram_notification_event_kind",
        ),
        sa.CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND failed_at IS NULL) "
            "OR (status = 'RUNNING' AND started_at IS NOT NULL AND failed_at IS NULL) "
            "OR (status = 'FAILED' AND started_at IS NOT NULL AND failed_at IS NOT NULL)",
            name="ck_telegram_notification_status_timestamps",
        ),
        sa.CheckConstraint(
            "(status = 'FAILED' AND error_code IS NOT NULL) OR "
            "(status <> 'FAILED' AND error_code IS NULL AND error_message IS NULL)",
            name="ck_telegram_notification_error_fields",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_snapshot_id"],
            ["analysis_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["previous_analysis_snapshot_id"],
            ["analysis_snapshots.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "analysis_snapshot_id",
            name="uq_telegram_notification_user_analysis_snapshot",
        ),
    )
    op.create_index(
        "ix_telegram_notification_pending",
        "telegram_notification_outbox",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_notification_pending",
        table_name="telegram_notification_outbox",
    )
    op.drop_table("telegram_notification_outbox")
    op.drop_table("telegram_bot_state")
    op.drop_table("telegram_connections")
