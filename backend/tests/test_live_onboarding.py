from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AnalysisChartSnapshot,
    AnalysisSnapshot,
    AppUser,
    BenchmarkDailyCandle,
    Company,
    DailyCandle as StoredDailyCandle,
    Instrument,
    MarketBenchmark,
    ProviderInstrumentIdentity,
    TrackedInstrument,
    TrackingOperationalState,
    UserRole,
    UserWatchlistItem,
)
from app.providers.contracts import DailyCandle, ExchangeSession
from app.providers.errors import ProviderError
from app.domain.technical_analysis import (
    IncompleteCandleHistoryError,
    InsufficientListingHistoryError,
    PersistentCandleGapError,
)
from app.services.live_onboarding import (
    LiveOnboardingHandler,
    _should_notify_setup_change,
)
from app.services.onboarding_worker import ClaimedOnboardingJob


def test_only_automatic_analysis_can_notify_setup_changes() -> None:
    assert _should_notify_setup_change(
        telegram_notifications_enabled=True,
        reuse_stored_market_data=False,
    )
    assert not _should_notify_setup_change(
        telegram_notifications_enabled=True,
        reuse_stored_market_data=True,
    )
    assert not _should_notify_setup_change(
        telegram_notifications_enabled=False,
        reuse_stored_market_data=False,
    )


class FakeProvider:
    def __init__(
        self,
        candles: tuple[DailyCandle, ...],
        benchmark: tuple[DailyCandle, ...],
        intraday: dict[str, tuple[DailyCandle, ...]] | None = None,
    ) -> None:
        self.candles = candles
        self.benchmark = benchmark
        self.requested_keys: list[str] = []
        self.requested_ranges: list[tuple[str, date, date]] = []
        self.intraday = intraday or {}
        self.intraday_requests: list[str] = []

    async def get_daily_candles(
        self,
        **kwargs: object,
    ) -> tuple[DailyCandle, ...]:
        instrument_key = str(kwargs["instrument_key"])
        self.requested_keys.append(instrument_key)
        from_date = kwargs["from_date"]
        to_date = kwargs["to_date"]
        assert isinstance(from_date, date)
        assert isinstance(to_date, date)
        self.requested_ranges.append((instrument_key, from_date, to_date))
        source = (
            self.benchmark
            if instrument_key == "NSE_INDEX|Nifty 500"
            else self.candles
        )
        return tuple(
            item
            for item in source
            if from_date <= item.trading_date <= to_date
        )

    async def get_nse_session(self, session_date: date) -> ExchangeSession:
        return ExchangeSession(
            session_date=session_date,
            is_open=session_date in {
                item.trading_date for item in self.benchmark
            },
        )

    async def get_intraday_daily_candles(
        self,
        *,
        instrument_key: str,
    ) -> tuple[DailyCandle, ...]:
        self.intraday_requests.append(instrument_key)
        return self.intraday.get(instrument_key, ())


class FailingStockProvider(FakeProvider):
    def __init__(
        self,
        candles: tuple[DailyCandle, ...],
        benchmark: tuple[DailyCandle, ...],
        *,
        fail_stock: bool = True,
    ) -> None:
        super().__init__(candles, benchmark)
        self.fail_stock = fail_stock
        self.intraday_attempts: list[str] = []

    async def get_daily_candles(
        self,
        **kwargs: object,
    ) -> tuple[DailyCandle, ...]:
        instrument_key = str(kwargs["instrument_key"])
        if self.fail_stock and instrument_key != "NSE_INDEX|Nifty 500":
            raise ProviderError(code="UPSTOX_RATE_LIMITED", retryable=True)
        return await super().get_daily_candles(**kwargs)

    async def get_intraday_daily_candles(
        self,
        *,
        instrument_key: str,
    ) -> tuple[DailyCandle, ...]:
        self.intraday_attempts.append(instrument_key)
        if self.fail_stock and instrument_key != "NSE_INDEX|Nifty 500":
            raise ProviderError(code="UPSTOX_RATE_LIMITED", retryable=True)
        return await super().get_intraday_daily_candles(
            instrument_key=instrument_key
        )


def synthetic_candles() -> tuple[DailyCandle, ...]:
    start = date(2025, 1, 1)
    result: list[DailyCandle] = []
    for index in range(320):
        session_date = start + timedelta(days=index)
        if index < 260:
            close = Decimal("100") + Decimal(index)
            high = close + Decimal("2")
            low = close - Decimal("2")
        else:
            base_index = index - 260
            if base_index < 40:
                close = Decimal("360") + Decimal(base_index % 4)
                high = close + Decimal("3")
                low = close - Decimal("3")
            elif base_index < 50:
                close = Decimal("360") + Decimal(base_index - 40) * Decimal("0.4")
                high = close + Decimal("2.5")
                low = close - Decimal("2.5")
            else:
                close = Decimal("364") + Decimal(base_index - 50) * Decimal("0.4")
                high = close + Decimal("0.5")
                low = close - Decimal("0.5")
        result.append(
            DailyCandle(
                trading_date=session_date,
                timestamp=datetime.combine(session_date, datetime.min.time(), tzinfo=UTC),
                open=close - Decimal("0.2"),
                high=high,
                low=low,
                close=close,
                volume=1000,
                open_interest=0,
            )
        )
    for index in (265, 280, 295):
        session_date = start + timedelta(days=index)
        result[index] = DailyCandle(
            trading_date=session_date,
            timestamp=datetime.combine(session_date, datetime.min.time(), tzinfo=UTC),
            open=Decimal("366"),
            high=Decimal("370"),
            low=Decimal("363"),
            close=Decimal("365"),
            volume=1000,
            open_interest=0,
        )
    return tuple(result)


def synthetic_benchmark(
    candles: tuple[DailyCandle, ...],
) -> tuple[DailyCandle, ...]:
    result: list[DailyCandle] = []
    for index, candle in enumerate(candles):
        if index < 260:
            close = Decimal("100") + Decimal(index) * Decimal("0.10")
        else:
            close = Decimal("126") - Decimal(index - 260) * Decimal("0.07")
        result.append(
            DailyCandle(
                trading_date=candle.trading_date,
                timestamp=candle.timestamp,
                open=close,
                high=close + Decimal("0.1"),
                low=close - Decimal("0.1"),
                close=close,
                volume=1000,
                open_interest=0,
            )
        )
    return tuple(result)


async def build_failure_case(
    db_session: AsyncSession,
    *,
    candles: tuple[DailyCandle, ...],
    benchmark: tuple[DailyCandle, ...],
    symbol: str,
    provider: FakeProvider | None = None,
) -> tuple[LiveOnboardingHandler, ClaimedOnboardingJob, Instrument]:
    occurred_at = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    instrument = Instrument(
        company=Company(name=f"{symbol} Industries Limited"),
        exchange="NSE",
        trading_symbol=symbol,
    )
    tracking = TrackedInstrument(
        instrument=instrument,
        operational_state=TrackingOperationalState.PREPARING,
        target_session=benchmark[-1].trading_date,
        created_at=occurred_at,
        updated_at=occurred_at,
    )
    db_session.add(tracking)
    await db_session.flush()
    db_session.add(
        ProviderInstrumentIdentity(
            instrument_id=instrument.id,
            provider="UPSTOX",
            instrument_key=f"NSE_EQ|{symbol}",
            isin="INE123A01010",
            effective_from=candles[0].trading_date,
            source_fetched_at=occurred_at,
        )
    )
    await db_session.flush()

    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    handler = LiveOnboardingHandler(
        session_factory=factory,
        provider=provider or FakeProvider(candles, benchmark),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        clock=lambda: occurred_at,
    )
    job = ClaimedOnboardingJob(
        job_id=1,
        tracked_instrument_id=tracking.id,
        instrument_id=instrument.id,
        target_session=benchmark[-1].trading_date,
        attempt_count=1,
    )
    return handler, job, instrument


@pytest.mark.anyio
async def test_handler_persists_candles_before_analysis(
    db_session: AsyncSession,
) -> None:
    candles = synthetic_candles()
    created_at = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
    completed_at = datetime(2026, 7, 25, 11, 0, tzinfo=UTC)
    instrument = Instrument(
        company=Company(name="Example Industries Limited"),
        exchange="NSE",
        trading_symbol="EXAMPLE",
    )
    tracking = TrackedInstrument(
        instrument=instrument,
        operational_state=TrackingOperationalState.PREPARING,
        target_session=candles[-1].trading_date,
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(tracking)
    await db_session.flush()
    user = AppUser(
        username="onboarding-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    db_session.add(user)
    await db_session.flush()
    membership = UserWatchlistItem(
        user_id=user.id,
        instrument_id=instrument.id,
        baseline_session=candles[-1].trading_date,
        baseline_close_price=None,
    )
    db_session.add(membership)
    db_session.add(
        ProviderInstrumentIdentity(
            instrument_id=instrument.id,
            provider="UPSTOX",
            instrument_key="NSE_EQ|INE002A01018",
            isin="INE002A01018",
            effective_from=candles[0].trading_date,
            source_fetched_at=created_at,
        )
    )
    await db_session.flush()

    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    provider = FakeProvider(candles, synthetic_benchmark(candles))
    handler = LiveOnboardingHandler(
        session_factory=factory,
        provider=provider,
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        clock=lambda: completed_at,
    )

    await handler(
        ClaimedOnboardingJob(
            job_id=1,
            tracked_instrument_id=tracking.id,
            instrument_id=instrument.id,
            target_session=candles[-1].trading_date,
            attempt_count=1,
        )
    )

    snapshot = await db_session.scalar(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.instrument_id == instrument.id
        )
    )
    benchmark = await db_session.scalar(
        select(MarketBenchmark).where(
            MarketBenchmark.code == "NIFTY_500"
        )
    )
    benchmark_candle_count = await db_session.scalar(
        select(func.count()).select_from(BenchmarkDailyCandle)
    )
    await db_session.refresh(tracking)
    await db_session.refresh(membership)
    assert provider.requested_keys == [
        "NSE_INDEX|Nifty 500",
        "NSE_EQ|INE002A01018",
    ]
    assert snapshot is not None
    assert snapshot.source == "UPSTOX"
    assert snapshot.algorithm_version == "technical-v19"
    assert snapshot.setup_score is not None
    assert snapshot.stage2_score is not None
    assert snapshot.rejection_reasons is not None
    charts = list(
        await db_session.scalars(
            select(AnalysisChartSnapshot).where(
                AnalysisChartSnapshot.analysis_snapshot_id == snapshot.id
            )
        )
    )
    assert len(charts) == 1
    chart = charts[0]
    assert chart.timeframe == "DAILY"
    assert chart.period_count == snapshot.consolidation_window
    assert chart.window_start == snapshot.consolidation_start
    assert chart.window_end == snapshot.analysis_date
    assert chart.schema_version == "technical-chart-v3"
    assert 20 <= len(chart.candles) <= 130
    assert chart.resistance_zone_lower < chart.resistance_price
    assert chart.resistance_zone_upper > chart.resistance_price
    assert benchmark is not None
    assert benchmark.instrument_key == "NSE_INDEX|Nifty 500"
    assert benchmark_candle_count == len(candles)
    assert tracking.operational_state == TrackingOperationalState.READY
    assert membership.baseline_close_price == candles[-1].close

    provider.requested_keys.clear()
    provider.requested_ranges.clear()
    await handler(
        ClaimedOnboardingJob(
            job_id=2,
            tracked_instrument_id=tracking.id,
            instrument_id=instrument.id,
            target_session=candles[-1].trading_date,
            attempt_count=1,
            reuse_stored_market_data=True,
        )
    )
    assert provider.requested_ranges == []
    assert provider.intraday_requests == []


@pytest.mark.anyio
async def test_handler_fetches_only_an_internal_missing_stock_session(
    db_session: AsyncSession,
) -> None:
    candles = synthetic_candles()
    created_at = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
    instrument = Instrument(
        company=Company(name="Gap Industries Limited"),
        exchange="NSE",
        trading_symbol="GAP",
    )
    tracking = TrackedInstrument(
        instrument=instrument,
        operational_state=TrackingOperationalState.PREPARING,
        target_session=candles[-1].trading_date,
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(tracking)
    await db_session.flush()
    db_session.add(
        ProviderInstrumentIdentity(
            instrument_id=instrument.id,
            provider="UPSTOX",
            instrument_key="NSE_EQ|INE999A01010",
            isin="INE999A01010",
            effective_from=candles[0].trading_date,
            source_fetched_at=created_at,
        )
    )
    await db_session.flush()

    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    provider = FakeProvider(candles, synthetic_benchmark(candles))
    handler = LiveOnboardingHandler(
        session_factory=factory,
        provider=provider,
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        clock=lambda: created_at,
    )
    job = ClaimedOnboardingJob(
        job_id=1,
        tracked_instrument_id=tracking.id,
        instrument_id=instrument.id,
        target_session=candles[-1].trading_date,
        attempt_count=1,
    )
    await handler(job)

    missing_date = candles[100].trading_date
    await db_session.execute(
        delete(StoredDailyCandle).where(
            StoredDailyCandle.instrument_id == instrument.id,
            StoredDailyCandle.trading_date == missing_date,
        )
    )
    await db_session.commit()
    provider.requested_ranges.clear()

    await handler(job)

    stock_requests = [
        item
        for item in provider.requested_ranges
        if item[0] == "NSE_EQ|INE999A01010"
    ]
    assert stock_requests == [
        ("NSE_EQ|INE999A01010", missing_date, missing_date)
    ]


@pytest.mark.anyio
async def test_handler_uses_completed_intraday_candle_then_finalizes_it(
    db_session: AsyncSession,
) -> None:
    candles = synthetic_candles()
    benchmark_candles = synthetic_benchmark(candles)
    target = candles[-1].trading_date
    fetched_at = datetime.combine(
        target,
        datetime.min.time(),
        tzinfo=UTC,
    ) + timedelta(hours=12)
    instrument_key = "NSE_EQ|INE888A01011"
    benchmark_key = "NSE_INDEX|Nifty 500"
    instrument = Instrument(
        company=Company(name="Hybrid Industries Limited"),
        exchange="NSE",
        trading_symbol="HYBRID",
    )
    tracking = TrackedInstrument(
        instrument=instrument,
        operational_state=TrackingOperationalState.PREPARING,
        target_session=target,
        created_at=fetched_at,
        updated_at=fetched_at,
    )
    db_session.add(tracking)
    await db_session.flush()
    db_session.add(
        ProviderInstrumentIdentity(
            instrument_id=instrument.id,
            provider="UPSTOX",
            instrument_key=instrument_key,
            isin="INE888A01011",
            effective_from=candles[0].trading_date,
            source_fetched_at=fetched_at,
        )
    )
    await db_session.flush()

    provider = FakeProvider(
        candles[:-1],
        benchmark_candles[:-1],
        intraday={
            instrument_key: (candles[-1],),
            benchmark_key: (benchmark_candles[-1],),
        },
    )
    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    handler = LiveOnboardingHandler(
        session_factory=factory,
        provider=provider,
        benchmark_instrument_key=benchmark_key,
        clock=lambda: fetched_at,
    )
    job = ClaimedOnboardingJob(
        job_id=1,
        tracked_instrument_id=tracking.id,
        instrument_id=instrument.id,
        target_session=target,
        attempt_count=1,
    )

    await handler(job)

    stock_today = await db_session.scalar(
        select(StoredDailyCandle).where(
            StoredDailyCandle.instrument_id == instrument.id,
            StoredDailyCandle.trading_date == target,
        )
    )
    benchmark_today = await db_session.scalar(
        select(BenchmarkDailyCandle).where(
            BenchmarkDailyCandle.trading_date == target,
        )
    )
    snapshot = await db_session.scalar(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.instrument_id == instrument.id,
            AnalysisSnapshot.analysis_date == target,
        )
    )
    assert stock_today is not None
    assert stock_today.source == "UPSTOX_INTRADAY"
    assert benchmark_today is not None
    assert benchmark_today.source == "UPSTOX_INTRADAY"
    assert snapshot is not None
    assert provider.intraday_requests == [benchmark_key, instrument_key]

    provider.candles = candles
    provider.benchmark = benchmark_candles
    provider.requested_ranges.clear()
    provider.intraday_requests.clear()
    await handler(job)

    await db_session.refresh(stock_today)
    await db_session.refresh(benchmark_today)
    assert stock_today.source == "UPSTOX"
    assert benchmark_today.source == "UPSTOX"
    assert provider.intraday_requests == []
    assert (instrument_key, target, target) in provider.requested_ranges
    assert (benchmark_key, target, target) in provider.requested_ranges


@pytest.mark.anyio
async def test_handler_persists_analysis_when_benchmark_is_unavailable(
    db_session: AsyncSession,
) -> None:
    candles = synthetic_candles()
    occurred_at = datetime(2026, 7, 25, 17, 0, tzinfo=UTC)
    instrument = Instrument(
        company=Company(name="No Benchmark Industries Limited"),
        exchange="NSE",
        trading_symbol="NOBENCH",
    )
    tracking = TrackedInstrument(
        instrument=instrument,
        operational_state=TrackingOperationalState.PREPARING,
        target_session=candles[-1].trading_date,
        created_at=occurred_at,
        updated_at=occurred_at,
    )
    db_session.add(tracking)
    await db_session.flush()
    db_session.add(
        ProviderInstrumentIdentity(
            instrument_id=instrument.id,
            provider="UPSTOX",
            instrument_key="NSE_EQ|INE777A01012",
            isin="INE777A01012",
            effective_from=candles[0].trading_date,
            source_fetched_at=occurred_at,
        )
    )
    await db_session.flush()

    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    handler = LiveOnboardingHandler(
        session_factory=factory,
        provider=FakeProvider(candles, ()),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        clock=lambda: occurred_at,
    )

    await handler(
        ClaimedOnboardingJob(
            job_id=99,
            tracked_instrument_id=tracking.id,
            instrument_id=instrument.id,
            target_session=candles[-1].trading_date,
            attempt_count=1,
        )
    )

    snapshot = await db_session.scalar(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.instrument_id == instrument.id
        )
    )
    assert snapshot is not None
    assert snapshot.algorithm_version == "technical-v19"
    assert snapshot.relative_strength_score is None


@pytest.mark.anyio
async def test_handler_uses_previous_analysis_when_latest_stock_candle_unavailable(
    db_session: AsyncSession,
) -> None:
    candles = synthetic_candles()
    benchmark = synthetic_benchmark(candles)
    provider = FailingStockProvider(candles, benchmark, fail_stock=False)
    handler, job, instrument = await build_failure_case(
        db_session,
        candles=candles,
        benchmark=benchmark,
        symbol="STALELATEST",
        provider=provider,
    )
    await handler(job)

    previous_session = candles[-1].trading_date
    target_session = previous_session + timedelta(days=1)
    latest_benchmark = benchmark[-1]
    provider.benchmark = benchmark + (
        DailyCandle(
            trading_date=target_session,
            timestamp=datetime.combine(
                target_session,
                datetime.min.time(),
                tzinfo=UTC,
            ),
            open=latest_benchmark.open,
            high=latest_benchmark.high,
            low=latest_benchmark.low,
            close=latest_benchmark.close,
            volume=latest_benchmark.volume,
            open_interest=latest_benchmark.open_interest,
        ),
    )
    provider.fail_stock = True

    await handler(
        ClaimedOnboardingJob(
            job_id=2,
            tracked_instrument_id=job.tracked_instrument_id,
            instrument_id=instrument.id,
            target_session=target_session,
            attempt_count=1,
        )
    )

    tracking = await db_session.get(TrackedInstrument, job.tracked_instrument_id)
    latest_analysis_date = await db_session.scalar(
        select(func.max(AnalysisSnapshot.analysis_date)).where(
            AnalysisSnapshot.instrument_id == instrument.id
        )
    )
    assert tracking is not None
    await db_session.refresh(tracking)
    assert tracking.operational_state == TrackingOperationalState.READY
    assert tracking.target_session == previous_session
    assert latest_analysis_date == previous_session
    assert f"NSE_EQ|STALELATEST" not in provider.intraday_attempts


@pytest.mark.anyio
async def test_handler_retries_provider_error_without_stored_stock_history(
    db_session: AsyncSession,
) -> None:
    candles = synthetic_candles()
    benchmark = synthetic_benchmark(candles)
    provider = FailingStockProvider(candles, benchmark)
    handler, job, _ = await build_failure_case(
        db_session,
        candles=candles,
        benchmark=benchmark,
        symbol="NOSTORED",
        provider=provider,
    )

    with pytest.raises(ProviderError) as captured:
        await handler(job)

    assert captured.value.code == "UPSTOX_RATE_LIMITED"
    assert captured.value.retryable is True


@pytest.mark.anyio
async def test_short_continuous_listing_history_is_persisted_and_classified(
    db_session: AsyncSession,
) -> None:
    full_history = synthetic_candles()
    short_history = full_history[-100:]
    handler, job, instrument = await build_failure_case(
        db_session,
        candles=short_history,
        benchmark=synthetic_benchmark(full_history),
        symbol="NEWLISTING",
    )

    with pytest.raises(InsufficientListingHistoryError, match="252 are required"):
        await handler(job)

    stored_count = await db_session.scalar(
        select(func.count())
        .select_from(StoredDailyCandle)
        .where(StoredDailyCandle.instrument_id == instrument.id)
    )
    snapshot_count = await db_session.scalar(
        select(func.count())
        .select_from(AnalysisSnapshot)
        .where(AnalysisSnapshot.instrument_id == instrument.id)
    )
    assert stored_count == len(short_history)
    assert snapshot_count == 0


@pytest.mark.anyio
async def test_internal_gap_is_persistent_but_preserves_other_fetched_candles(
    db_session: AsyncSession,
) -> None:
    full_history = synthetic_candles()
    missing_session = full_history[100].trading_date
    gapped_history = tuple(
        candle
        for candle in full_history
        if candle.trading_date != missing_session
    )
    handler, job, instrument = await build_failure_case(
        db_session,
        candles=gapped_history,
        benchmark=synthetic_benchmark(full_history),
        symbol="GAPPED",
    )

    with pytest.raises(PersistentCandleGapError, match=missing_session.isoformat()):
        await handler(job)

    stored_dates = set(
        await db_session.scalars(
            select(StoredDailyCandle.trading_date).where(
                StoredDailyCandle.instrument_id == instrument.id
            )
        )
    )
    assert len(stored_dates) == len(gapped_history)
    assert missing_session not in stored_dates
