from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.status import AnalysisJobStatus, AnalysisJobType


if TYPE_CHECKING:
    from app.models.tracked_instrument import TrackedInstrument


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_analysis_jobs_attempt_count_non_negative",
        ),
        CheckConstraint(
            "next_attempt_at >= created_at",
            name="ck_analysis_jobs_next_attempt_at",
        ),
        CheckConstraint(
            (
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
                "AND completed_at IS NOT NULL)"
            ),
            name="ck_analysis_jobs_status_timestamps",
        ),
        CheckConstraint(
            (
                "started_at IS NULL "
                "OR started_at >= created_at"
            ),
            name="ck_analysis_jobs_started_at",
        ),
        CheckConstraint(
            (
                "completed_at IS NULL "
                "OR (started_at IS NULL AND completed_at >= created_at) "
                "OR completed_at >= started_at"
            ),
            name="ck_analysis_jobs_completed_at",
        ),
        CheckConstraint(
            (
                "(status = 'FAILED' AND error_code IS NOT NULL) "
                "OR (status <> 'FAILED' "
                "AND error_code IS NULL "
                "AND error_message IS NULL)"
            ),
            name="ck_analysis_jobs_error_fields",
        ),
        CheckConstraint(
            (
                "error_code IS NULL "
                "OR (error_code = btrim(error_code) "
                "AND error_code = upper(error_code) "
                "AND error_code <> '')"
            ),
            name="ck_analysis_jobs_error_code_normalized",
        ),
        CheckConstraint(
            (
                "error_message IS NULL "
                "OR (error_message = btrim(error_message) "
                "AND error_message <> '')"
            ),
            name="ck_analysis_jobs_error_message_normalized",
        ),
        Index(
            "uq_analysis_jobs_one_active_per_type",
            "tracked_instrument_id",
            "job_type",
            unique=True,
            postgresql_where=text(
                "status IN ('PENDING', 'RUNNING')"
            ),
        ),
        Index(
            "ix_analysis_jobs_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "ix_analysis_jobs_pending_schedule",
            "status",
            "next_attempt_at",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    tracked_instrument_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "tracked_instruments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    job_type: Mapped[AnalysisJobType] = mapped_column(
        SqlEnum(
            AnalysisJobType,
            name="ck_analysis_jobs_job_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=32,
        ),
        nullable=False,
    )
    target_session: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    status: Mapped[AnalysisJobStatus] = mapped_column(
        SqlEnum(
            AnalysisJobStatus,
            name="ck_analysis_jobs_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    reuse_stored_market_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    tracked_instrument: Mapped["TrackedInstrument"] = relationship(
        back_populates="analysis_jobs",
    )
