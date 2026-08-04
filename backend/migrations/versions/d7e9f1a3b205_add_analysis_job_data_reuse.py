"""Add stored-market-data reuse intent to analysis jobs.

Revision ID: d7e9f1a3b205
Revises: c6b8e4d2f901
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d7e9f1a3b205"
down_revision: str | Sequence[str] | None = "c6b8e4d2f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_jobs",
        sa.Column(
            "reuse_stored_market_data",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("analysis_jobs", "reuse_stored_market_data")
