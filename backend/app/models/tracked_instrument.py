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
    Integer,
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.status import TrackingOperationalState


if TYPE_CHECKING:
    from app.models.analysis_job import AnalysisJob
    from app.models.instrument import Instrument


class TrackedInstrument(Base):
    __tablename__ = "tracked_instruments"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            name="uq_tracked_instruments_instrument_id",
        ),
        CheckConstraint(
            (
                "(is_active AND deactivated_at IS NULL) "
                "OR (NOT is_active AND deactivated_at IS NOT NULL)"
            ),
            name="ck_tracked_instruments_active_deactivated_at",
        ),
        CheckConstraint(
            (
                "reactivated_at IS NULL "
                "OR reactivated_at >= created_at"
            ),
            name="ck_tracked_instruments_reactivated_at",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_tracked_instruments_updated_at",
        ),
        CheckConstraint(
            "(terminal_data_error_session IS NULL AND terminal_data_error_code IS NULL) "
            "OR (terminal_data_error_session IS NOT NULL "
            "AND terminal_data_error_code IS NOT NULL)",
            name="ck_tracked_instruments_terminal_data_error_pair",
        ),
        CheckConstraint(
            "terminal_data_error_code IS NULL "
            "OR (terminal_data_error_code = upper(btrim(terminal_data_error_code)) "
            "AND terminal_data_error_code <> '')",
            name="ck_tracked_instruments_terminal_data_error_code",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    instrument_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "instruments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    operational_state: Mapped[
        TrackingOperationalState
    ] = mapped_column(
        SqlEnum(
            TrackingOperationalState,
            name="ck_tracked_instruments_operational_state",
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
    terminal_data_error_session: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    terminal_data_error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    instrument: Mapped["Instrument"] = relationship(
        back_populates="tracked_instrument",
    )
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(
        back_populates="tracked_instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
