"""Mark instruments that predate the temporary bulk scan.

Revision ID: c6b8e4d2f901
Revises: a2c4e6f8b010
Create Date: 2026-07-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c6b8e4d2f901"
down_revision: str | Sequence[str] | None = "a2c4e6f8b010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column(
            "is_preexisting_before_bulk_scan",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("instruments", "is_preexisting_before_bulk_scan")
