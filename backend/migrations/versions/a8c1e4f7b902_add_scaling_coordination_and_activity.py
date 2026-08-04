"""Add scaling coordination and user activity.

Revision ID: a8c1e4f7b902
Revises: f5b7d9a1c324
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a8c1e4f7b902"
down_revision: str | Sequence[str] | None = "f5b7d9a1c324"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_users",
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_app_users_last_active_at",
        "app_users",
        ["last_active_at"],
    )
    op.create_table(
        "distributed_rate_limit_buckets",
        sa.Column("bucket_key", sa.String(length=160), nullable=False),
        sa.Column(
            "next_permit_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "bucket_key = btrim(bucket_key) AND bucket_key <> ''",
            name="ck_distributed_rate_limit_bucket_key",
        ),
        sa.PrimaryKeyConstraint("bucket_key"),
    )


def downgrade() -> None:
    op.drop_table("distributed_rate_limit_buckets")
    op.drop_index("ix_app_users_last_active_at", table_name="app_users")
    op.drop_column("app_users", "last_active_at")
