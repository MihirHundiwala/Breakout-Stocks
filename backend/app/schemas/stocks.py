from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.status import (
    FundamentalCoverageStatus,
    TechnicalStatus,
    TrackingOperationalState,
)


class StockListItem(BaseModel):
    instrument_id: int
    company_name: str
    exchange: str
    trading_symbol: str
    analysis_date: date | None
    technical_status: TechnicalStatus | None
    fundamental_coverage: FundamentalCoverageStatus
    close_price: Decimal | None
    day_change_percent: Decimal | None
    setup_score: Decimal | None = None
    stage2_score: Decimal | None = None
    relative_strength_score: Decimal | None = None
    base_quality_score: Decimal | None = None
    volatility_contraction_score: Decimal | None = None
    volume_contraction_score: Decimal | None = None
    resistance_quality_score: Decimal | None = None
    proximity_score: Decimal | None = None
    closing_quality_score: Decimal | None = None
    consolidation_window: int | None = None
    consolidation_timeframe: str | None = None
    consolidation_start: date | None = None
    base_high: Decimal | None = None
    base_low: Decimal | None = None
    base_depth_pct: Decimal | None = None
    base_position: Decimal | None = None
    high_26_week: Decimal | None = None
    tightness_pass_count: int | None = None
    resistance: Decimal | None = None
    resistance_touch_count: int | None = None
    resistance_dispersion_pct: Decimal | None = None
    resistance_touch_dates: list[date] = Field(default_factory=list)
    distance_to_resistance_pct: Decimal | None = None
    atr14: Decimal | None = None
    atr_pct: Decimal | None = None
    atr_contraction_ratio: Decimal | None = None
    return_volatility_ratio: Decimal | None = None
    daily_range_ratio: Decimal | None = None
    ma_spread: Decimal | None = None
    volume_dryup_ratio: Decimal | None = None
    breakout_volume_ratio: Decimal | None = None
    distribution_day_count: int | None = None
    close_location_value: Decimal | None = None
    breakout_extension_atr: Decimal | None = None
    rejection_reasons: list[str] = Field(default_factory=list)
    market_cap_crore: Decimal | None
    source: str | None
    source_fetched_at: datetime | None
    algorithm_version: str | None
    has_chart_data: bool = False
    operational_state: TrackingOperationalState
    analysis_error_session: date | None = None
    analysis_error_code: str | None = None


class StockListResponse(BaseModel):
    items: list[StockListItem]
    count: int
    page: int
    page_size: int
    total_pages: int


class FundamentalSnapshotDetail(BaseModel):
    as_of_date: date
    coverage: FundamentalCoverageStatus
    available_group_count: int
    expected_group_count: int
    metrics: dict[str, object]
    source: str
    source_fetched_at: datetime
    schema_version: str


class FundamentalPeriodDetail(BaseModel):
    period_end: date
    period_kind: str
    statement_basis: str
    currency: str
    metrics: dict[str, object]
    source_fetched_at: datetime
    schema_version: str


class StockDetailResponse(BaseModel):
    stock: StockListItem
    fundamentals: FundamentalSnapshotDetail | None
    periods: list[FundamentalPeriodDetail]


class AnalysisChartCandle(BaseModel):
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0)


class AnalysisChartSlide(BaseModel):
    timeframe: str
    technical_status: TechnicalStatus
    period_count: int
    resistance_price: Decimal
    resistance_zone_lower: Decimal
    resistance_zone_upper: Decimal
    resistance_touch_dates: list[date]
    candles: list[AnalysisChartCandle] = Field(min_length=20, max_length=130)
    schema_version: str


class AnalysisChartResponse(BaseModel):
    instrument_id: int
    company_name: str
    trading_symbol: str
    analysis_date: date
    technical_status: TechnicalStatus
    charts: list[AnalysisChartSlide] = Field(min_length=1, max_length=2)
