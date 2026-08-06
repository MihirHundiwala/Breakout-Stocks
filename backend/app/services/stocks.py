from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market_math import percentage_change
from app.models import FundamentalCoverageStatus, TrackingOperationalState
from app.repositories.stocks import (
    StockSort,
    get_stock_detail_record,
    get_stock_chart_record,
    list_latest_stock_analyses,
)
from app.schemas.stocks import (
    FundamentalPeriodDetail,
    FundamentalSnapshotDetail,
    StockDetailResponse,
    AnalysisChartCandle,
    AnalysisChartResponse,
    StockListItem,
    StockListResponse,
)


class StockAnalysisNotFoundError(LookupError):
    pass


class StockChartNotFoundError(LookupError):
    pass


def _stock_item(
    company,
    instrument,
    snapshot,
    market_cap_crore=None,
    latest_fundamental_coverage=None,
    has_chart_data: bool = False,
    operational_state: TrackingOperationalState | None = None,
    analysis_error_session: date | None = None,
    analysis_error_code: str | None = None,
) -> StockListItem:
    resolved_operational_state = operational_state or (
        TrackingOperationalState.READY
        if snapshot is not None
        else TrackingOperationalState.PREPARING
    )
    if snapshot is None:
        return StockListItem(
            instrument_id=instrument.id,
            company_name=company.name,
            exchange=instrument.exchange,
            trading_symbol=instrument.trading_symbol,
            analysis_date=None,
            technical_status=None,
            fundamental_coverage=(
                latest_fundamental_coverage
                or FundamentalCoverageStatus.UNKNOWN
            ),
            close_price=None,
            day_change_percent=None,
            market_cap_crore=market_cap_crore,
            source=None,
            source_fetched_at=None,
            algorithm_version=None,
            has_chart_data=False,
            operational_state=resolved_operational_state,
            analysis_error_session=analysis_error_session,
            analysis_error_code=analysis_error_code,
        )
    return StockListItem(
        instrument_id=instrument.id,
        company_name=company.name,
        exchange=instrument.exchange,
        trading_symbol=instrument.trading_symbol,
        analysis_date=snapshot.analysis_date,
        technical_status=snapshot.technical_status,
        fundamental_coverage=(
            latest_fundamental_coverage or snapshot.fundamental_coverage
        ),
        close_price=snapshot.close_price,
        day_change_percent=percentage_change(
            snapshot.close_price,
            snapshot.previous_close_price,
        ),
        setup_score=snapshot.setup_score,
        stage2_score=snapshot.stage2_score,
        relative_strength_score=snapshot.relative_strength_score,
        base_quality_score=snapshot.base_quality_score,
        volatility_contraction_score=(
            snapshot.volatility_contraction_score
        ),
        volume_contraction_score=snapshot.volume_contraction_score,
        resistance_quality_score=snapshot.resistance_quality_score,
        proximity_score=snapshot.proximity_score,
        closing_quality_score=snapshot.closing_quality_score,
        consolidation_window=snapshot.consolidation_window,
        consolidation_timeframe=snapshot.consolidation_timeframe,
        consolidation_start=snapshot.consolidation_start,
        base_high=snapshot.base_high,
        base_low=snapshot.base_low,
        base_depth_pct=snapshot.base_depth_pct,
        base_position=snapshot.base_position,
        high_26_week=snapshot.high_26_week,
        tightness_pass_count=snapshot.tightness_pass_count,
        resistance=snapshot.resistance_price,
        resistance_touch_count=snapshot.resistance_touch_count,
        resistance_dispersion_pct=snapshot.resistance_dispersion_pct,
        resistance_touch_dates=snapshot.resistance_touch_dates or [],
        distance_to_resistance_pct=snapshot.distance_to_resistance_pct,
        atr14=snapshot.atr14,
        atr_pct=snapshot.atr_pct,
        atr_contraction_ratio=snapshot.atr_contraction_ratio,
        return_volatility_ratio=snapshot.return_volatility_ratio,
        daily_range_ratio=snapshot.daily_range_ratio,
        ma_spread=snapshot.ma_spread,
        volume_dryup_ratio=snapshot.volume_dryup_ratio,
        breakout_volume_ratio=snapshot.breakout_volume_ratio,
        distribution_day_count=snapshot.distribution_day_count,
        close_location_value=snapshot.close_location_value,
        breakout_extension_atr=snapshot.breakout_extension_atr,
        rejection_reasons=snapshot.rejection_reasons or [],
        market_cap_crore=market_cap_crore,
        source=snapshot.source,
        source_fetched_at=snapshot.source_fetched_at,
        algorithm_version=snapshot.algorithm_version,
        has_chart_data=has_chart_data,
        operational_state=resolved_operational_state,
        analysis_error_session=analysis_error_session,
        analysis_error_code=analysis_error_code,
    )


async def get_stock_list(
    session: AsyncSession,
    *,
    user_id: int,
    is_admin: bool,
    page: int,
    page_size: int | None,
    search: str | None,
    sort: StockSort,
) -> StockListResponse:
    result = await list_latest_stock_analyses(
        session,
        user_id=user_id,
        is_admin=is_admin,
        page=page,
        page_size=page_size,
        search=search,
        sort=sort,
    )
    items: list[StockListItem] = []

    for (
        company,
        instrument,
        snapshot,
        market_cap_crore,
        latest_fundamental_coverage,
        has_chart_data,
        operational_state,
        analysis_error_session,
        analysis_error_code,
    ) in result.records:
        items.append(
            _stock_item(
                company,
                instrument,
                snapshot,
                market_cap_crore,
                latest_fundamental_coverage,
                has_chart_data,
                operational_state,
                analysis_error_session,
                analysis_error_code,
            )
        )

    effective_page_size = result.count if page_size is None else page_size
    total_pages = (
        1
        if result.count and page_size is None
        else (
            (result.count + effective_page_size - 1)
            // effective_page_size
            if result.count
            else 0
        )
    )
    return StockListResponse(
        items=items,
        count=result.count,
        page=page,
        page_size=effective_page_size,
        total_pages=total_pages,
    )


async def get_stock_detail(
    session: AsyncSession,
    instrument_id: int,
    *,
    user_id: int,
    is_admin: bool,
) -> StockDetailResponse:
    record = await get_stock_detail_record(
        session,
        instrument_id,
        user_id=user_id,
        is_admin=is_admin,
    )
    if record is None:
        raise StockAnalysisNotFoundError(instrument_id)

    fundamental_detail = None
    if record.fundamentals is not None:
        item = record.fundamentals
        fundamental_detail = FundamentalSnapshotDetail(
            as_of_date=item.as_of_date,
            coverage=item.coverage,
            available_group_count=item.available_metric_count,
            expected_group_count=item.expected_metric_count,
            metrics=item.metrics,
            source=item.source,
            source_fetched_at=item.source_fetched_at,
            schema_version=item.schema_version,
        )

    profile = (
        record.fundamentals.metrics.get("profile")
        if record.fundamentals is not None
        else None
    )
    market_cap_crore = (
        profile.get("sector_market_cap_inr_crore")
        if isinstance(profile, dict)
        else None
    )
    return StockDetailResponse(
        stock=_stock_item(
            record.company,
            record.instrument,
            record.analysis,
            market_cap_crore,
            has_chart_data=record.has_chart_data,
        ),
        fundamentals=fundamental_detail,
        periods=[
            FundamentalPeriodDetail(
                period_end=period.period_end,
                period_kind=period.period_kind,
                statement_basis=period.statement_basis,
                currency=period.currency,
                metrics=period.metrics,
                source_fetched_at=period.source_fetched_at,
                schema_version=period.schema_version,
            )
            for period in record.periods
        ],
    )


async def get_stock_chart(
    session: AsyncSession,
    instrument_id: int,
    *,
    user_id: int,
    is_admin: bool,
) -> AnalysisChartResponse:
    record = await get_stock_chart_record(
        session,
        instrument_id,
        user_id=user_id,
        is_admin=is_admin,
    )
    if record is None:
        raise StockChartNotFoundError(instrument_id)
    return AnalysisChartResponse(
        instrument_id=record.instrument.id,
        company_name=record.company.name,
        trading_symbol=record.instrument.trading_symbol,
        analysis_date=record.analysis.analysis_date,
        technical_status=record.analysis.technical_status,
        charts=[
            {
                "timeframe": chart.timeframe,
                "technical_status": (
                    chart.technical_status or record.analysis.technical_status
                ),
                "period_count": chart.period_count,
                "resistance_price": chart.resistance_price,
                "resistance_zone_lower": chart.resistance_zone_lower,
                "resistance_zone_upper": chart.resistance_zone_upper,
                "resistance_touch_dates": chart.resistance_touch_dates,
                "candles": [
                    AnalysisChartCandle.model_validate(item)
                    for item in chart.candles
                ],
                "schema_version": chart.schema_version,
            }
            for chart in record.charts
        ],
    )
