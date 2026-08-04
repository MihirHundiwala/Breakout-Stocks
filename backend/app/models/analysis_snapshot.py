from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.status import (
    FundamentalCoverageStatus,
    TechnicalStatus,
)


if TYPE_CHECKING:
    from app.models.analysis_chart_snapshot import AnalysisChartSnapshot
    from app.models.instrument import Instrument


class AnalysisSnapshot(Base):
    __tablename__ = "analysis_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "analysis_date",
            "algorithm_version",
            "candle_revision",
            name=(
                "uq_analysis_snapshots_"
                "instrument_date_version_revision"
            ),
        ),
        CheckConstraint(
            "close_price > 0",
            name="ck_analysis_snapshots_close_positive",
        ),
        CheckConstraint(
            "previous_close_price > 0",
            name="ck_analysis_snapshots_previous_close_positive",
        ),
        CheckConstraint(
            "setup_score IS NULL OR (setup_score >= 0 AND setup_score <= 100)",
            name="ck_analysis_snapshots_setup_score_range",
        ),
        CheckConstraint(
            "stage2_score IS NULL OR (stage2_score >= 0 AND stage2_score <= 1)",
            name="ck_analysis_snapshots_stage2_score_range",
        ),
        CheckConstraint(
            (
                "relative_strength_score IS NULL OR "
                "(relative_strength_score >= 0 AND relative_strength_score <= 1)"
            ),
            name="ck_analysis_snapshots_rs_score_range",
        ),
        CheckConstraint(
            "pivot_price IS NULL OR pivot_price > 0",
            name="ck_analysis_snapshots_pivot_positive",
        ),
        CheckConstraint(
            "pivot_price IS NULL AND breakout_confirmed_on IS NULL",
            name="ck_analysis_snapshots_status_fields",
        ),
        CheckConstraint(
            (
                "breakout_confirmed_on IS NULL "
                "OR breakout_confirmed_on <= analysis_date"
            ),
            name="ck_analysis_snapshots_confirmation_date",
        ),
        CheckConstraint(
            (
                "source = btrim(source) "
                "AND source = upper(source) "
                "AND source <> ''"
            ),
            name="ck_analysis_snapshots_source_normalized",
        ),
        CheckConstraint(
            (
                "algorithm_version = btrim(algorithm_version) "
                "AND algorithm_version <> ''"
            ),
            name="ck_analysis_snapshots_algorithm_version",
        ),
        CheckConstraint(
            (
                "candle_revision = btrim(candle_revision) "
                "AND candle_revision <> ''"
            ),
            name="ck_analysis_snapshots_candle_revision",
        ),
        CheckConstraint(
            "consolidation_timeframe IS NULL "
            "OR consolidation_timeframe IN ('DAILY', 'WEEKLY')",
            name="ck_analysis_snapshots_consolidation_timeframe",
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
    analysis_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    technical_status: Mapped[TechnicalStatus] = mapped_column(
        SqlEnum(
            TechnicalStatus,
            name="ck_analysis_snapshots_technical_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=32,
        ),
        nullable=False,
    )
    fundamental_coverage: Mapped[
        FundamentalCoverageStatus
    ] = mapped_column(
        SqlEnum(
            FundamentalCoverageStatus,
            name="ck_analysis_snapshots_fundamental_coverage",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=False,
    )
    close_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )
    previous_close_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )
    setup_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    stage2_score: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    relative_strength_score: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6)
    )
    base_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    volatility_contraction_score: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6)
    )
    volume_contraction_score: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6)
    )
    resistance_quality_score: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6)
    )
    proximity_score: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    closing_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    consolidation_window: Mapped[int | None] = mapped_column(Integer)
    consolidation_timeframe: Mapped[str | None] = mapped_column(String(16))
    consolidation_start: Mapped[date | None] = mapped_column(Date)
    base_high: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    base_low: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    base_depth_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    base_position: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    high_26_week: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    tightness_pass_count: Mapped[int | None] = mapped_column(Integer)
    resistance_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    resistance_touch_count: Mapped[int | None] = mapped_column(Integer)
    resistance_dispersion_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8)
    )
    resistance_touch_dates: Mapped[list[str] | None] = mapped_column(JSON)
    distance_to_resistance_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8)
    )
    atr14: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    atr_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    atr_contraction_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8)
    )
    return_volatility_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8)
    )
    daily_range_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    ma_spread: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    volume_dryup_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    breakout_volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    distribution_day_count: Mapped[int | None] = mapped_column(Integer)
    close_location_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    breakout_extension_atr: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8)
    )
    average_traded_value_20: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    rejection_reasons: Mapped[list[str] | None] = mapped_column(JSON)
    pivot_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
    )
    breakout_confirmed_on: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    source_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    candle_revision: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    instrument: Mapped["Instrument"] = relationship(
        back_populates="analysis_snapshots",
    )
    chart_snapshots: Mapped[list["AnalysisChartSnapshot"]] = relationship(
        back_populates="analysis_snapshot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
