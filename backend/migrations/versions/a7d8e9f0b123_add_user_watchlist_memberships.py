"""Add users and per-user watchlist memberships.

Revision ID: a7d8e9f0b123
Revises: f1a6c3b9d204
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a7d8e9f0b123"
down_revision: str | Sequence[str] | None = "f1a6c3b9d204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "username = btrim(username) AND username = lower(username) AND username <> ''",
            name="ck_app_users_username_normalized",
        ),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'USER')",
            name="ck_app_users_role",
        ),
        sa.CheckConstraint(
            "(role = 'ADMIN' AND password_hash IS NULL) OR "
            "(role = 'USER' AND password_hash IS NOT NULL "
            "AND password_hash LIKE '$argon2%')",
            name="ck_app_users_role_password_hash",
        ),
        sa.CheckConstraint("updated_at >= created_at", name="ck_app_users_updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_app_users_username"),
    )
    op.create_index(
        "uq_app_users_single_admin",
        "app_users",
        ["role"],
        unique=True,
        postgresql_where=sa.text("role = 'ADMIN'"),
    )
    op.execute(
        "INSERT INTO app_users (username, role, password_hash) "
        "VALUES ('admin', 'ADMIN', NULL)"
    )

    op.create_table(
        "user_watchlist_items",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(is_active AND deactivated_at IS NULL) OR "
            "(NOT is_active AND deactivated_at IS NOT NULL)",
            name="ck_user_watchlist_items_active_deactivated_at",
        ),
        sa.CheckConstraint(
            "reactivated_at IS NULL OR reactivated_at >= created_at",
            name="ck_user_watchlist_items_reactivated_at",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ck_user_watchlist_items_updated_at",
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "instrument_id",
            name="uq_user_watchlist_items_user_instrument",
        ),
    )
    op.create_index(
        "ix_user_watchlist_items_user_active",
        "user_watchlist_items",
        ["user_id", "is_active"],
    )
    op.create_index(
        "ix_user_watchlist_items_active_instrument",
        "user_watchlist_items",
        ["instrument_id"],
        postgresql_where=sa.text("is_active"),
    )
    op.execute(
        "INSERT INTO user_watchlist_items "
        "(user_id, instrument_id, is_active, created_at, updated_at, "
        "deactivated_at, reactivated_at) "
        "SELECT users.id, tracking.instrument_id, tracking.is_active, "
        "tracking.created_at, tracking.updated_at, tracking.deactivated_at, "
        "tracking.reactivated_at "
        "FROM tracked_instruments AS tracking "
        "CROSS JOIN app_users AS users "
        "WHERE users.username = 'admin'"
    )


def downgrade() -> None:
    connection = op.get_bind()
    normal_user_count = connection.scalar(
        sa.text("SELECT count(*) FROM app_users WHERE role <> 'ADMIN'")
    )
    if normal_user_count:
        raise RuntimeError(
            "Cannot downgrade while normal users exist; the previous schema "
            "cannot represent their watchlists."
        )

    op.drop_index(
        "ix_user_watchlist_items_active_instrument",
        table_name="user_watchlist_items",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_index(
        "ix_user_watchlist_items_user_active",
        table_name="user_watchlist_items",
    )
    op.drop_table("user_watchlist_items")
    op.drop_index(
        "uq_app_users_single_admin",
        table_name="app_users",
        postgresql_where=sa.text("role = 'ADMIN'"),
    )
    op.drop_table("app_users")
