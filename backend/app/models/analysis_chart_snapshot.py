from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Enum as SqlEnum, ForeignKey, Identity, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.status import TechnicalStatus


if TYPE_CHECKING:
    from app.models.analysis_snapshot import AnalysisSnapshot


class AnalysisChartSnapshot(Base):
    """Immutable visual evidence for one versioned technical analysis."""

    __tablename__ = "analysis_chart_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "analysis_snapshot_id",
            "timeframe",
            name="uq_analysis_chart_snapshots_analysis_timeframe",
        ),
        CheckConstraint(
            "window_start <= window_end",
            name="ck_analysis_chart_snapshots_window",
        ),
        CheckConstraint(
            "resistance_zone_lower > 0 "
            "AND resistance_price >= resistance_zone_lower "
            "AND resistance_zone_upper >= resistance_price",
            name="ck_analysis_chart_snapshots_resistance_zone",
        ),
        CheckConstraint(
            "jsonb_typeof(candles) = 'array' "
            "AND jsonb_array_length(candles) BETWEEN 20 AND 130",
            name="ck_analysis_chart_snapshots_candles",
        ),
        CheckConstraint(
            "jsonb_typeof(resistance_touch_dates) = 'array'",
            name="ck_analysis_chart_snapshots_touch_dates",
        ),
        CheckConstraint(
            "schema_version = btrim(schema_version) AND schema_version <> ''",
            name="ck_analysis_chart_snapshots_schema_version",
        ),
        CheckConstraint(
            "(timeframe = 'DAILY' AND period_count BETWEEN 20 AND 120) OR "
            "(timeframe = 'WEEKLY' AND period_count BETWEEN 26 AND 104)",
            name="ck_analysis_chart_snapshots_timeframe_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    analysis_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    technical_status: Mapped[TechnicalStatus | None] = mapped_column(
        SqlEnum(
            TechnicalStatus,
            name="ck_analysis_chart_snapshots_technical_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=32,
        ),
        nullable=True,
    )
    period_count: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    resistance_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    resistance_zone_lower: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    resistance_zone_upper: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    resistance_touch_dates: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    candles: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    analysis_snapshot: Mapped["AnalysisSnapshot"] = relationship(
        back_populates="chart_snapshots"
    )
