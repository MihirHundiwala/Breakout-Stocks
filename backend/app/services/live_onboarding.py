from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256

from sqlalchemy import desc, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.technical_analysis import (
    IncompleteCandleHistoryError,
    InsufficientListingHistoryError,
    PersistentCandleGapError,
    TechnicalAnalysisResult,
    analyze_technical_setup,
    required_candle_sessions,
)
from app.models import (
    AnalysisChartSnapshot,
    AnalysisJob,
    AnalysisSnapshot,
    BenchmarkDailyCandle,
    DailyCandle,
    FundamentalCoverageStatus,
    FundamentalSnapshot,
    TechnicalStatus,
    TrackedInstrument,
    TrackingOperationalState,
    UserWatchlistItem,
)
from app.providers.contracts import DailyCandle as ProviderCandle
from app.providers.contracts import (
    AnalysisMarketDataProvider,
    ExchangeCalendarProvider,
    MarketDataProvider,
)
from app.providers.errors import ProviderError
from app.repositories.live_data import (
    ensure_market_benchmark,
    get_active_provider_identity,
    list_benchmark_daily_candles,
    list_daily_candles,
    upsert_daily_candles,
    upsert_benchmark_daily_candles,
)
from app.services.market_sessions import NSE_TIMEZONE
from app.services.onboarding_worker import ClaimedOnboardingJob
from app.services.setup_notifications import (
    enqueue_pending_watchlist_setup_notifications,
    enqueue_setup_change_notification,
    get_previous_setup_state,
)


class LiveOnboardingError(RuntimeError):
    pass


NIFTY_500_BENCHMARK_CODE = "NIFTY_500"
NIFTY_500_BENCHMARK_NAME = "Nifty 500"
ANALYSIS_HISTORY_CALENDAR_DAYS = 600
HISTORICAL_CANDLE_SOURCE = "UPSTOX"
INTRADAY_CANDLE_SOURCE = "UPSTOX_INTRADAY"
CHART_SCHEMA_VERSION = "technical-chart-v3"


def _should_notify_setup_change(
    *,
    telegram_notifications_enabled: bool,
    reuse_stored_market_data: bool,
) -> bool:
    return telegram_notifications_enabled and not reuse_stored_market_data


def _revision(
    candles: list[ProviderCandle],
    benchmark_candles: list[ProviderCandle],
) -> str:
    value = "|".join(
        f"{series}:{item.trading_date}:{item.open}:{item.high}:"
        f"{item.low}:{item.close}:{item.volume}"
        for series, series_candles in (
            ("stock", candles),
            ("nifty500", benchmark_candles),
        )
        for item in series_candles
    )
    return sha256(value.encode("utf-8")).hexdigest()[:32]


def _chart_values(
    candles: list[ProviderCandle],
    *,
    result: TechnicalAnalysisResult,
    generated_at: datetime,
) -> list[dict[str, object]]:
    if (
        result.status == TechnicalStatus.NO_SETUP
        or result.consolidation_start is None
        or result.resistance_price is None
        or result.resistance_zone_lower is None
        or result.resistance_zone_upper is None
    ):
        return []
    if result.chart_evidence:
        return [
            {
                "timeframe": evidence.timeframe,
                "period_count": evidence.period_count,
                "window_start": evidence.candles[0].trading_date,
                "window_end": evidence.candles[-1].trading_date,
                "resistance_price": evidence.resistance_price,
                "resistance_zone_lower": evidence.resistance_zone_lower,
                "resistance_zone_upper": evidence.resistance_zone_upper,
                "resistance_touch_dates": [
                    item.isoformat() for item in evidence.resistance_touch_dates
                ],
                "candles": [
                    {
                        "date": item.trading_date.isoformat(),
                        "open": str(item.open),
                        "high": str(item.high),
                        "low": str(item.low),
                        "close": str(item.close),
                        "volume": item.volume,
                    }
                    for item in evidence.candles
                ],
                "schema_version": CHART_SCHEMA_VERSION,
                "generated_at": generated_at,
            }
            for evidence in result.chart_evidence
            if 20 <= len(evidence.candles) <= 130
        ]
    selected = [
        item
        for item in candles
        if result.consolidation_start
        <= item.trading_date
        <= result.analysis_date
    ]
    if not 20 <= len(selected) <= 130:
        return []
    return [{
        "timeframe": result.consolidation_timeframe or "DAILY",
        "period_count": result.consolidation_window or len(selected) - 1,
        "window_start": selected[0].trading_date,
        "window_end": selected[-1].trading_date,
        "resistance_price": result.resistance_price,
        "resistance_zone_lower": result.resistance_zone_lower,
        "resistance_zone_upper": result.resistance_zone_upper,
        "resistance_touch_dates": [
            item.isoformat() for item in result.resistance_touch_dates
        ],
        "candles": [
            {
                "date": item.trading_date.isoformat(),
                "open": str(item.open),
                "high": str(item.high),
                "low": str(item.low),
                "close": str(item.close),
                "volume": item.volume,
            }
            for item in selected
        ],
        "schema_version": CHART_SCHEMA_VERSION,
        "generated_at": generated_at,
    }]


def _to_provider_candle(
    candle: DailyCandle | BenchmarkDailyCandle,
) -> ProviderCandle:
    return ProviderCandle(
        trading_date=candle.trading_date,
        timestamp=candle.source_timestamp,
        open=candle.open_price,
        high=candle.high_price,
        low=candle.low_price,
        close=candle.close_price,
        volume=candle.volume,
        open_interest=candle.open_interest,
    )


def _merge_candles(
    stored: list[ProviderCandle],
    fetched: list[ProviderCandle],
) -> list[ProviderCandle]:
    by_date = {item.trading_date: item for item in stored}
    by_date.update({item.trading_date: item for item in fetched})
    return [by_date[item] for item in sorted(by_date)]


def _missing_session_ranges(
    expected_sessions: list[date],
    present_sessions: set[date],
) -> list[tuple[date, date]]:
    ranges: list[tuple[date, date]] = []
    range_start: date | None = None
    range_end: date | None = None
    for session_date in expected_sessions:
        if session_date in present_sessions:
            if range_start is not None and range_end is not None:
                ranges.append((range_start, range_end))
                range_start = range_end = None
            continue
        if range_start is None:
            range_start = session_date
        range_end = session_date
    if range_start is not None and range_end is not None:
        ranges.append((range_start, range_end))
    return ranges


async def _expected_sessions(
    provider: ExchangeCalendarProvider,
    *,
    from_date: date,
    to_date: date,
    known_open_sessions: set[date],
) -> list[date]:
    expected: list[date] = []
    candidate = from_date
    while candidate <= to_date:
        if candidate in known_open_sessions:
            expected.append(candidate)
        elif candidate.weekday() < 5:
            session = await provider.get_nse_session(candidate)
            if session.is_open:
                expected.append(candidate)
        candidate += timedelta(days=1)
    return expected


async def _fetch_candle_ranges(
    provider: MarketDataProvider,
    *,
    instrument_key: str,
    ranges: list[tuple[date, date]],
) -> list[ProviderCandle]:
    fetched: list[ProviderCandle] = []
    for range_start, range_end in ranges:
        fetched.extend(
            await provider.get_daily_candles(
                instrument_key=instrument_key,
                from_date=range_start,
                to_date=range_end,
            )
        )
    return fetched


class LiveOnboardingHandler:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        provider: AnalysisMarketDataProvider,
        benchmark_instrument_key: str,
        telegram_notifications_enabled: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._benchmark_instrument_key = benchmark_instrument_key
        self._telegram_notifications_enabled = telegram_notifications_enabled
        self._clock = clock

    async def _persist_fetched_market_data(
        self,
        *,
        job: ClaimedOnboardingJob,
        fetched_stock: list[ProviderCandle],
        intraday_stock: list[ProviderCandle],
        fetched_benchmark: list[ProviderCandle],
        intraday_benchmark: list[ProviderCandle],
        fetched_at: datetime,
        persist_stock: bool,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                tracking = await session.scalar(
                    select(TrackedInstrument)
                    .where(TrackedInstrument.id == job.tracked_instrument_id)
                    .with_for_update()
                )
                if tracking is None or not tracking.is_active:
                    raise LiveOnboardingError("TRACKING_CANCELLED")

                if persist_stock:
                    await upsert_daily_candles(
                        session,
                        instrument_id=job.instrument_id,
                        candles=tuple(fetched_stock),
                        fetched_at=fetched_at,
                    )
                    await upsert_daily_candles(
                        session,
                        instrument_id=job.instrument_id,
                        candles=tuple(intraday_stock),
                        fetched_at=fetched_at,
                        source=INTRADAY_CANDLE_SOURCE,
                    )

                benchmark = await ensure_market_benchmark(
                    session,
                    code=NIFTY_500_BENCHMARK_CODE,
                    name=NIFTY_500_BENCHMARK_NAME,
                    provider="UPSTOX",
                    instrument_key=self._benchmark_instrument_key,
                    source_fetched_at=fetched_at,
                )
                await upsert_benchmark_daily_candles(
                    session,
                    benchmark_id=benchmark.id,
                    candles=tuple(fetched_benchmark),
                    fetched_at=fetched_at,
                )
                await upsert_benchmark_daily_candles(
                    session,
                    benchmark_id=benchmark.id,
                    candles=tuple(intraday_benchmark),
                    fetched_at=fetched_at,
                    source=INTRADAY_CANDLE_SOURCE,
                )

    async def __call__(self, job: ClaimedOnboardingJob) -> None:
        current_nse_date = self._clock().astimezone(NSE_TIMEZONE).date()
        async with self._session_factory() as session:
            identity = await get_active_provider_identity(
                session,
                job.instrument_id,
                "UPSTOX",
            )
        if identity is None:
            raise LiveOnboardingError("ACTIVE_PROVIDER_IDENTITY_REQUIRED")

        from_date = job.target_session - timedelta(
            days=ANALYSIS_HISTORY_CALENDAR_DAYS
        )
        async with self._session_factory() as session:
            stored_stock_rows = await list_daily_candles(
                session,
                instrument_id=job.instrument_id,
                from_date=from_date,
                to_date=job.target_session,
            )
            stored_stock = [
                _to_provider_candle(item)
                for item in stored_stock_rows
            ]
            stored_benchmark_rows = await list_benchmark_daily_candles(
                session,
                benchmark_code=NIFTY_500_BENCHMARK_CODE,
                from_date=from_date,
                to_date=job.target_session,
            )
            stored_benchmark = [
                _to_provider_candle(item)
                for item in stored_benchmark_rows
            ]
            historical_stock_dates = {
                item.trading_date
                for item in stored_stock_rows
                if (
                    job.reuse_stored_market_data
                    or item.source == HISTORICAL_CANDLE_SOURCE
                )
            }
            historical_benchmark_dates = {
                item.trading_date
                for item in stored_benchmark_rows
                if (
                    job.reuse_stored_market_data
                    or item.source == HISTORICAL_CANDLE_SOURCE
                )
            }

        if job.reuse_stored_market_data:
            benchmark_ranges: list[tuple[date, date]] = []
        elif stored_benchmark:
            expected_dates = await _expected_sessions(
                self._provider,
                from_date=from_date,
                to_date=job.target_session,
                known_open_sessions={
                    item.trading_date for item in stored_benchmark
                },
            )
            benchmark_ranges = _missing_session_ranges(
                expected_dates,
                historical_benchmark_dates,
            )
        else:
            benchmark_ranges = [(from_date, job.target_session)]

        try:
            fetched_benchmark = await _fetch_candle_ranges(
                self._provider,
                instrument_key=self._benchmark_instrument_key,
                ranges=benchmark_ranges,
            )
        except ProviderError:
            # Relative strength is a required technical-v19 component. Stock
            # analysis remains valid when the benchmark provider is unavailable.
            fetched_benchmark = []
        benchmark_candles = _merge_candles(
            stored_benchmark,
            fetched_benchmark,
        )
        intraday_benchmark: list[ProviderCandle] = []
        if (
            not job.reuse_stored_market_data
            and job.target_session == current_nse_date
            and job.target_session
            not in {item.trading_date for item in benchmark_candles}
        ):
            try:
                intraday_benchmark = [
                    item
                    for item in await self._provider.get_intraday_daily_candles(
                        instrument_key=self._benchmark_instrument_key,
                    )
                    if item.trading_date == job.target_session
                ]
            except ProviderError:
                intraday_benchmark = []
            benchmark_candles = _merge_candles(
                benchmark_candles,
                intraday_benchmark,
            )
        expected_dates = await _expected_sessions(
            self._provider,
            from_date=from_date,
            to_date=job.target_session,
            known_open_sessions={
                item.trading_date for item in benchmark_candles
            },
        )
        if job.reuse_stored_market_data:
            stock_ranges: list[tuple[date, date]] = []
            stock_base = stored_stock
        elif not stored_stock:
            stock_ranges = [(from_date, job.target_session)]
            stock_base: list[ProviderCandle] = []
        else:
            stock_ranges = _missing_session_ranges(
                expected_dates,
                historical_stock_dates,
            )
            stock_base = stored_stock
        try:
            fetched_stock = await _fetch_candle_ranges(
                self._provider,
                instrument_key=identity.instrument_key,
                ranges=stock_ranges,
            )
        except ProviderError as error:
            if not stored_stock or not error.retryable:
                raise
            fetched_stock = []
        domain_candles = _merge_candles(stock_base, fetched_stock)
        intraday_stock: list[ProviderCandle] = []
        if (
            not job.reuse_stored_market_data
            and job.target_session == current_nse_date
            and job.target_session
            not in {item.trading_date for item in domain_candles}
        ):
            try:
                intraday_stock = [
                    item
                    for item in await self._provider.get_intraday_daily_candles(
                        instrument_key=identity.instrument_key,
                    )
                    if item.trading_date == job.target_session
                ]
            except ProviderError as error:
                if not stored_stock or not error.retryable:
                    raise
                intraday_stock = []
            domain_candles = _merge_candles(
                domain_candles,
                intraday_stock,
            )
        if not domain_candles:
            raise IncompleteCandleHistoryError(
                "Upstox returned no stock history in the retained window."
            )
        effective_target = min(
            job.target_session,
            domain_candles[-1].trading_date,
        )
        domain_candles = [
            item for item in domain_candles if item.trading_date <= effective_target
        ]
        benchmark_candles = [
            item
            for item in benchmark_candles
            if item.trading_date <= effective_target
        ]
        effective_expected_dates = [
            item
            for item in expected_dates
            if domain_candles[0].trading_date <= item <= effective_target
        ]

        fetched_at = self._clock()
        await self._persist_fetched_market_data(
            job=job,
            fetched_stock=fetched_stock,
            intraday_stock=intraday_stock,
            fetched_benchmark=fetched_benchmark,
            intraday_benchmark=intraday_benchmark,
            fetched_at=fetched_at,
            persist_stock=True,
        )

        missing_stock = set(effective_expected_dates).difference(
            item.trading_date for item in domain_candles
        )
        if missing_stock:
            missing_dates = sorted(missing_stock)
            raise PersistentCandleGapError(
                "Upstox omitted internal completed sessions after a successful "
                f"gap fetch: {', '.join(item.isoformat() for item in missing_dates[:5])}."
            )
        required_sessions = required_candle_sessions()
        if len(domain_candles) < required_sessions:
            raise InsufficientListingHistoryError(
                f"Only {len(domain_candles)} complete candles are available; "
                f"{required_sessions} are required."
            )

        result = analyze_technical_setup(
            domain_candles,
            benchmark_candles=benchmark_candles,
            target_session=effective_target,
            expected_sessions=effective_expected_dates,
        )
        revision = _revision(domain_candles, benchmark_candles)

        async with self._session_factory() as session:
            async with session.begin():
                tracking = await session.scalar(
                    select(TrackedInstrument)
                    .where(TrackedInstrument.id == job.tracked_instrument_id)
                    .with_for_update()
                )
                if tracking is None or not tracking.is_active:
                    raise LiveOnboardingError("TRACKING_CANCELLED")

                if effective_target != job.target_session:
                    persisted_job = await session.scalar(
                        select(AnalysisJob)
                        .where(AnalysisJob.id == job.job_id)
                        .with_for_update()
                    )
                    if persisted_job is not None:
                        persisted_job.target_session = effective_target

                fundamental_coverage = await session.scalar(
                    select(FundamentalSnapshot.coverage)
                    .where(
                        FundamentalSnapshot.instrument_id == job.instrument_id,
                        FundamentalSnapshot.as_of_date <= effective_target,
                    )
                    .order_by(
                        desc(FundamentalSnapshot.as_of_date),
                        desc(FundamentalSnapshot.source_fetched_at),
                    )
                    .limit(1)
                ) or FundamentalCoverageStatus.UNKNOWN

                # Stored-data jobs are explicit administrator algorithm reruns.
                # They update research without replaying user alerts.
                should_notify = _should_notify_setup_change(
                    telegram_notifications_enabled=(
                        self._telegram_notifications_enabled
                    ),
                    reuse_stored_market_data=job.reuse_stored_market_data,
                )
                previous_setup = (
                    await get_previous_setup_state(
                        session,
                        instrument_id=job.instrument_id,
                    )
                    if should_notify
                    else None
                )

                snapshot_id = await session.scalar(
                    insert(AnalysisSnapshot)
                    .values(
                        instrument_id=job.instrument_id,
                        analysis_date=result.analysis_date,
                        technical_status=result.status,
                        fundamental_coverage=fundamental_coverage,
                        close_price=result.close_price,
                        previous_close_price=result.previous_close_price,
                        setup_score=result.setup_score,
                        stage2_score=result.stage2_score,
                        relative_strength_score=result.relative_strength_score,
                        base_quality_score=result.base_quality_score,
                        volatility_contraction_score=(
                            result.volatility_contraction_score
                        ),
                        volume_contraction_score=(
                            result.volume_contraction_score
                        ),
                        resistance_quality_score=(
                            result.resistance_quality_score
                        ),
                        proximity_score=result.proximity_score,
                        closing_quality_score=result.closing_quality_score,
                        consolidation_window=result.consolidation_window,
                        consolidation_timeframe=result.consolidation_timeframe,
                        consolidation_start=result.consolidation_start,
                        base_high=result.base_high,
                        base_low=result.base_low,
                        base_depth_pct=result.base_depth_pct,
                        base_position=result.base_position,
                        high_26_week=result.high_26_week,
                        tightness_pass_count=result.tightness_pass_count,
                        resistance_price=result.resistance_price,
                        resistance_touch_count=(
                            result.resistance_touch_count
                        ),
                        resistance_dispersion_pct=(
                            result.resistance_dispersion_pct
                        ),
                        resistance_touch_dates=[
                            item.isoformat()
                            for item in result.resistance_touch_dates
                        ],
                        distance_to_resistance_pct=(
                            result.distance_to_resistance_pct
                        ),
                        atr14=result.atr14,
                        atr_pct=result.atr_pct,
                        atr_contraction_ratio=(
                            result.atr_contraction_ratio
                        ),
                        return_volatility_ratio=(
                            result.return_volatility_ratio
                        ),
                        daily_range_ratio=result.daily_range_ratio,
                        ma_spread=result.ma_spread,
                        volume_dryup_ratio=result.volume_dryup_ratio,
                        breakout_volume_ratio=(
                            result.breakout_volume_ratio
                        ),
                        distribution_day_count=(
                            result.distribution_day_count
                        ),
                        close_location_value=result.close_location_value,
                        breakout_extension_atr=(
                            result.breakout_extension_atr
                        ),
                        average_traded_value_20=(
                            result.average_traded_value_20
                        ),
                        rejection_reasons=list(result.rejection_reasons),
                        pivot_price=None,
                        breakout_confirmed_on=None,
                        source="UPSTOX",
                        source_fetched_at=fetched_at,
                        algorithm_version=result.algorithm_version,
                        candle_revision=revision,
                        generated_at=fetched_at,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_analysis_snapshots_instrument_date_version_revision"
                    )
                    .returning(AnalysisSnapshot.id)
                )
                snapshot_inserted = snapshot_id is not None
                if snapshot_id is None:
                    snapshot_id = await session.scalar(
                        select(AnalysisSnapshot.id).where(
                            AnalysisSnapshot.instrument_id == job.instrument_id,
                            AnalysisSnapshot.analysis_date == result.analysis_date,
                            AnalysisSnapshot.algorithm_version == result.algorithm_version,
                            AnalysisSnapshot.candle_revision == revision,
                        )
                    )
                chart_values = _chart_values(
                    domain_candles,
                    result=result,
                    generated_at=fetched_at,
                )
                if snapshot_id is not None:
                    for chart in chart_values:
                        await session.execute(
                            insert(AnalysisChartSnapshot)
                            .values(
                                analysis_snapshot_id=snapshot_id,
                                **chart,
                            )
                            .on_conflict_do_nothing(
                                constraint=(
                                    "uq_analysis_chart_snapshots_analysis_timeframe"
                                )
                            )
                        )
                    if snapshot_inserted and should_notify:
                        newly_following_user_ids = (
                            await enqueue_pending_watchlist_setup_notifications(
                                session,
                                snapshot_id=snapshot_id,
                                current_status=result.status,
                                created_at=fetched_at,
                            )
                        )
                        await enqueue_setup_change_notification(
                            session,
                            snapshot_id=snapshot_id,
                            previous=previous_setup,
                            current_status=result.status,
                            chart_values=chart_values,
                            created_at=fetched_at,
                            excluded_user_ids=newly_following_user_ids,
                        )
                await session.execute(
                    update(UserWatchlistItem)
                    .where(
                        UserWatchlistItem.instrument_id == job.instrument_id,
                        UserWatchlistItem.is_active.is_(True),
                        UserWatchlistItem.baseline_session == result.analysis_date,
                        UserWatchlistItem.baseline_close_price.is_(None),
                    )
                    .values(
                        baseline_close_price=result.close_price,
                    )
                )
                tracking.operational_state = TrackingOperationalState.READY
                tracking.target_session = effective_target
                tracking.updated_at = fetched_at
