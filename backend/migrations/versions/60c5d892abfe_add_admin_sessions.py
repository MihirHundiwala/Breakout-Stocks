"""Add admin sessions.

Revision ID: 60c5d892abfe
Revises: 8708d03a2b4f
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "60c5d892abfe"
down_revision: str | Sequence[str] | None = "8708d03a2b4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_sessions",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column(
            "username",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "token_digest",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "csrf_token_digest",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "username = btrim(username) AND username <> ''",
            name="ck_admin_sessions_username_normalized",
        ),
        sa.CheckConstraint(
            "token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_admin_sessions_token_digest_hex",
        ),
        sa.CheckConstraint(
            "csrf_token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_admin_sessions_csrf_digest_hex",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_admin_sessions_expiry_after_creation",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_admin_sessions_revoked_after_creation",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_digest",
            name="uq_admin_sessions_token_digest",
        ),
    )
    op.create_index(
        "ix_admin_sessions_expires_at",
        "admin_sessions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_sessions_expires_at",
        table_name="admin_sessions",
    )
    op.drop_table("admin_sessions")
