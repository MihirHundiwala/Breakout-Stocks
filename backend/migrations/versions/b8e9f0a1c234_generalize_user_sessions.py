"""Generalize administrator sessions to user sessions.

Revision ID: b8e9f0a1c234
Revises: a7d8e9f0b123
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b8e9f0a1c234"
down_revision: str | Sequence[str] | None = "a7d8e9f0b123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("admin_sessions", "user_sessions")
    op.drop_constraint(
        "ck_admin_sessions_username_normalized",
        "user_sessions",
        type_="check",
    )
    op.add_column("user_sessions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE user_sessions AS sessions SET user_id = users.id "
        "FROM app_users AS users "
        "WHERE users.role = 'ADMIN' AND sessions.username = users.username"
    )
    missing_user_count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM user_sessions WHERE user_id IS NULL")
    )
    if missing_user_count:
        raise RuntimeError("Existing administrator sessions could not be assigned.")
    op.alter_column("user_sessions", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_user_sessions_user_id_app_users",
        "user_sessions",
        "app_users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("user_sessions", "username")
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "ck_admin_sessions_token_digest_hex TO ck_user_sessions_token_digest_hex"
    )
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "ck_admin_sessions_csrf_digest_hex TO ck_user_sessions_csrf_digest_hex"
    )
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "ck_admin_sessions_expiry_after_creation TO ck_user_sessions_expiry_after_creation"
    )
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "ck_admin_sessions_revoked_after_creation TO ck_user_sessions_revoked_after_creation"
    )
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "uq_admin_sessions_token_digest TO uq_user_sessions_token_digest"
    )
    op.execute(
        "ALTER INDEX ix_admin_sessions_expires_at RENAME TO ix_user_sessions_expires_at"
    )


def downgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column("username", sa.String(length=64), nullable=True),
    )
    op.execute(
        "UPDATE user_sessions AS sessions SET username = users.username "
        "FROM app_users AS users WHERE sessions.user_id = users.id"
    )
    op.alter_column("user_sessions", "username", nullable=False)
    op.create_check_constraint(
        "ck_admin_sessions_username_normalized",
        "user_sessions",
        "username = btrim(username) AND username <> ''",
    )
    op.drop_constraint(
        "fk_user_sessions_user_id_app_users",
        "user_sessions",
        type_="foreignkey",
    )
    op.drop_column("user_sessions", "user_id")
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "ck_user_sessions_token_digest_hex TO ck_admin_sessions_token_digest_hex"
    )
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "ck_user_sessions_csrf_digest_hex TO ck_admin_sessions_csrf_digest_hex"
    )
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "ck_user_sessions_expiry_after_creation TO ck_admin_sessions_expiry_after_creation"
    )
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "ck_user_sessions_revoked_after_creation TO ck_admin_sessions_revoked_after_creation"
    )
    op.execute(
        "ALTER TABLE user_sessions RENAME CONSTRAINT "
        "uq_user_sessions_token_digest TO uq_admin_sessions_token_digest"
    )
    op.execute(
        "ALTER INDEX ix_user_sessions_expires_at RENAME TO ix_admin_sessions_expires_at"
    )
    op.rename_table("user_sessions", "admin_sessions")
