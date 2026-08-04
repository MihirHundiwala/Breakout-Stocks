"""Add watchlist onboarding models.

Revision ID: 8708d03a2b4f
Revises: 20260723_0002
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "8708d03a2b4f"
down_revision: str | Sequence[str] | None = "20260723_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tracked_instruments",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "operational_state",
            sa.Enum(
                "PREPARING",
                "READY",
                "ANALYSIS_FAILED",
                name="ck_tracked_instruments_operational_state",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("target_session", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "reactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "(is_active AND deactivated_at IS NULL) "
            "OR (NOT is_active AND deactivated_at IS NOT NULL)",
            name="ck_tracked_instruments_active_deactivated_at",
        ),
        sa.CheckConstraint(
            "reactivated_at IS NULL "
            "OR reactivated_at >= created_at",
            name="ck_tracked_instruments_reactivated_at",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ck_tracked_instruments_updated_at",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            name="uq_tracked_instruments_instrument_id",
        ),
    )
    op.create_table(
        "analysis_jobs",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column(
            "tracked_instrument_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "job_type",
            sa.Enum(
                "ONBOARD_INSTRUMENT",
                name="ck_analysis_jobs_job_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("target_session", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                name="ck_analysis_jobs_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "error_code",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sa.String(length=512),
            nullable=True,
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_analysis_jobs_attempt_count_non_negative",
        ),
        sa.CheckConstraint(
            "(status = 'PENDING' "
            "AND started_at IS NULL "
            "AND completed_at IS NULL) "
            "OR (status = 'RUNNING' "
            "AND started_at IS NOT NULL "
            "AND completed_at IS NULL) "
            "OR (status IN ('SUCCEEDED', 'FAILED') "
            "AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL) "
            "OR (status = 'CANCELLED' "
            "AND completed_at IS NOT NULL)",
            name="ck_analysis_jobs_status_timestamps",
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="ck_analysis_jobs_started_at",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL "
            "OR (started_at IS NULL AND completed_at >= created_at) "
            "OR completed_at >= started_at",
            name="ck_analysis_jobs_completed_at",
        ),
        sa.CheckConstraint(
            "(status = 'FAILED' AND error_code IS NOT NULL) "
            "OR (status <> 'FAILED' "
            "AND error_code IS NULL "
            "AND error_message IS NULL)",
            name="ck_analysis_jobs_error_fields",
        ),
        sa.CheckConstraint(
            "error_code IS NULL "
            "OR (error_code = btrim(error_code) "
            "AND error_code = upper(error_code) "
            "AND error_code <> '')",
            name="ck_analysis_jobs_error_code_normalized",
        ),
        sa.CheckConstraint(
            "error_message IS NULL "
            "OR (error_message = btrim(error_message) "
            "AND error_message <> '')",
            name="ck_analysis_jobs_error_message_normalized",
        ),
        sa.ForeignKeyConstraint(
            ["tracked_instrument_id"],
            ["tracked_instruments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_jobs_status_created_at",
        "analysis_jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_analysis_jobs_one_active_per_type",
        "analysis_jobs",
        ["tracked_instrument_id", "job_type"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('PENDING', 'RUNNING')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_analysis_jobs_one_active_per_type",
        table_name="analysis_jobs",
        postgresql_where=sa.text(
            "status IN ('PENDING', 'RUNNING')"
        ),
    )
    op.drop_index(
        "ix_analysis_jobs_status_created_at",
        table_name="analysis_jobs",
    )
    op.drop_table("analysis_jobs")
    op.drop_table("tracked_instruments")
