"""Establish the database migration baseline.

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21
"""

from collections.abc import Sequence


revision: str = "20260721_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
