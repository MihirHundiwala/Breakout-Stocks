from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    AnalysisSnapshot,
    BenchmarkDailyCandle,
    Company,
    FundamentalCoverageStatus,
    Instrument,
    MarketBenchmark,
    TechnicalStatus,
)
from app.providers.contracts import DailyCandle, ExchangeSession
from app.services.nightly_scan import (
    schedule_active_watchlist,
    schedule_fundamental_refresh,
    schedule_latest_available_session,
    schedule_worker_startup,
)
from app.services.onboarding_worker import (
    claim_next_onboarding_job,
    complete_onboarding_job,
    fail_onboarding_job,
)
from app.services.watchlist import add_or_reactivate_instrument


NOW = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
TARGET = date(2026, 7, 24)


class OpenWeekdayMarket:
    def __init__(
        self,
        available_session: date = date(2026, 7, 27),
        intraday_session: date | None = None,
    ) -> None:
        self.available_session = available_session
        self.intraday_session = intraday_session

    async def get_nse_session(self, session_date: date) -> ExchangeSession:
        return ExchangeSession(
            session_date=session_date,
            is_open=session_date.weekday() < 5,
        )

    async def get_daily_candles(self, **_kwargs: object) -> tuple[DailyCandle, ...]:
        return (self._candle(self.available_session),)

    async def get_intraday_daily_candles(
        self,
        **_kwargs: object,
    ) -> tuple[DailyCandle, ...]:
        if self.intraday_session is None:
            return ()
        return (self._candle(self.intraday_session),)

    @staticmethod
    def _candle(session_date: date) -> DailyCandle:
        return DailyCandle(
            trading_date=session_date,
            timestamp=datetime.combine(
                session_date,
                datetime.min.time(),
                tzinfo=UTC,
            ),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1000,
            open_interest=0,
        )


async def persist_instrument(session: AsyncSession, symbol: str) -> Instrument:
    instrument = Instrument(
        company=Company(name=f"{symbol} Industries Limited"),
        exchange="NSE",
        trading_symbol=symbol,
    )
    session.add(instrument)
    await session.commit()
    return instrument


async def persist_analysis(
    session: AsyncSession,
    instrument_id: int,
    analysis_date: date,
) -> None:
    session.add(
        AnalysisSnapshot(
            instrument_id=instrument_id,
            analysis_date=analysis_date,
            technical_status=TechnicalStatus.NO_SETUP,
            fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
            close_price=Decimal("100"),
            previous_close_price=Decimal("99"),
            source="UPSTOX",
            source_fetched_at=NOW,
            algorithm_version="test-v1",
            candle_revision=f"revision-{analysis_date.isoformat()}",
            generated_at=NOW,
        )
    )
    await session.commit()


async def discard_pending_fundamental_jobs(session: AsyncSession) -> None:
    """Keep tests focused on technical scheduling when fundamentals are irrelevant."""
    await session.execute(
        delete(AnalysisJob).where(
            AnalysisJob.job_type == AnalysisJobType.REFRESH_FUNDAMENTALS
        )
    )
    await session.commit()


@pytest.mark.anyio
async def test_worker_startup_scheduling_can_be_disabled(
    db_session: AsyncSession,
) -> None:
    class ProviderMustNotBeCalled(OpenWeekdayMarket):
        async def get_nse_session(self, session_date: date) -> ExchangeSession:
            pytest.fail(f"Unexpected session lookup for {session_date}")

        async def get_daily_candles(
            self,
            **_kwargs: object,
        ) -> tuple[DailyCandle, ...]:
            pytest.fail("Unexpected candle lookup")

    result = await schedule_worker_startup(
        db_session,
        ProviderMustNotBeCalled(),
        enabled=False,
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        occurred_at=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
    )

    assert result is None


@pytest.mark.anyio
async def test_nightly_schedule_is_unlimited_and_skips_active_jobs(
    db_session: AsyncSession,
) -> None:
    for index in range(3):
        instrument = await persist_instrument(db_session, f"NIGHT{index}")
        await add_or_reactivate_instrument(
            db_session,
            instrument.id,
            TARGET,
            occurred_at=NOW,
        )

    result = await schedule_active_watchlist(
        db_session,
        target_session=TARGET,
        occurred_at=NOW,
    )

    assert result.enqueued_count == 0
    assert result.skipped_active_count == 3


@pytest.mark.anyio
async def test_technical_and_fundamental_jobs_are_scheduled_independently(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session, "INDEPENDENT")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        TARGET,
        occurred_at=NOW,
    )

    fundamentals = await schedule_fundamental_refresh(
        db_session,
        target_session=TARGET,
        occurred_at=NOW,
    )
    jobs = list(
        await db_session.scalars(select(AnalysisJob).order_by(AnalysisJob.id))
    )

    assert fundamentals.enqueued_count == 0
    assert fundamentals.skipped_active_count == 1
    assert [job.job_type for job in jobs] == [
        AnalysisJobType.ONBOARD_INSTRUMENT,
        AnalysisJobType.REFRESH_FUNDAMENTALS,
    ]


@pytest.mark.anyio
async def test_nightly_schedule_adds_analysis_after_onboarding_completed(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session, "NIGHTLY")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        TARGET,
        occurred_at=NOW,
    )
    claimed = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert claimed is not None
    await complete_onboarding_job(db_session, claimed.job_id, occurred_at=NOW)

    first = await schedule_active_watchlist(
        db_session,
        target_session=TARGET,
        occurred_at=NOW,
    )
    jobs = list(await db_session.scalars(select(AnalysisJob).order_by(AnalysisJob.id)))

    assert first.enqueued_count == 1
    assert jobs[-1].job_type == AnalysisJobType.ANALYZE_INSTRUMENT
    assert jobs[-1].status == AnalysisJobStatus.PENDING


@pytest.mark.anyio
async def test_forced_schedule_reanalyzes_a_completed_target_session(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session, "FORCED")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        TARGET,
        occurred_at=NOW,
    )
    await discard_pending_fundamental_jobs(db_session)
    onboarding = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert onboarding is not None
    await complete_onboarding_job(db_session, onboarding.job_id, occurred_at=NOW)

    scheduled = await schedule_active_watchlist(
        db_session,
        target_session=TARGET,
        occurred_at=NOW,
    )
    assert scheduled.enqueued_count == 1
    analysis = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert analysis is not None
    await persist_analysis(db_session, instrument.id, TARGET)
    await complete_onboarding_job(db_session, analysis.job_id, occurred_at=NOW)

    ordinary_repeat = await schedule_active_watchlist(
        db_session,
        target_session=TARGET,
        occurred_at=NOW,
    )
    forced_repeat = await schedule_active_watchlist(
        db_session,
        target_session=TARGET,
        force_reanalysis=True,
        reuse_stored_market_data=True,
        occurred_at=NOW,
    )
    jobs = list(
        await db_session.scalars(select(AnalysisJob).order_by(AnalysisJob.id))
    )

    assert ordinary_repeat.skipped_completed_count == 1
    assert forced_repeat.enqueued_count == 1
    assert forced_repeat.skipped_completed_count == 0
    assert jobs[-1].reuse_stored_market_data is True


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error_code",
    ("INSUFFICIENT_LISTING_HISTORY", "PERSISTENT_CANDLE_GAPS"),
)
async def test_terminal_data_failure_is_not_duplicated_for_same_session(
    db_session: AsyncSession,
    error_code: str,
) -> None:
    instrument = await persist_instrument(db_session, f"TERM{error_code[:4]}")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        TARGET,
        occurred_at=NOW,
    )
    await discard_pending_fundamental_jobs(db_session)
    onboarding = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert onboarding is not None
    await complete_onboarding_job(db_session, onboarding.job_id, occurred_at=NOW)
    await schedule_active_watchlist(
        db_session,
        target_session=TARGET,
        occurred_at=NOW,
    )
    analysis = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert analysis is not None
    await fail_onboarding_job(
        db_session,
        analysis.job_id,
        error_code,
        "Synthetic terminal data-quality result.",
        occurred_at=NOW,
    )

    repeated = await schedule_active_watchlist(
        db_session,
        target_session=TARGET,
        force_reanalysis=True,
        occurred_at=NOW,
    )
    next_session = await schedule_active_watchlist(
        db_session,
        target_session=date(2026, 7, 27),
        occurred_at=datetime(2026, 7, 27, 11, 0, tzinfo=UTC),
    )
    jobs = list(
        await db_session.scalars(select(AnalysisJob).order_by(AnalysisJob.id))
    )

    assert repeated.enqueued_count == 0
    assert repeated.skipped_terminal_count == 1
    assert next_session.enqueued_count == 1
    assert len(jobs) == 1


@pytest.mark.anyio
async def test_startup_schedule_targets_latest_available_session_once(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session, "STARTUP")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        TARGET,
        occurred_at=NOW,
    )
    await discard_pending_fundamental_jobs(db_session)
    onboarding = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert onboarding is not None
    await complete_onboarding_job(db_session, onboarding.job_id, occurred_at=NOW)

    after_market_close = datetime(2026, 7, 27, 11, 0, tzinfo=UTC)
    first = await schedule_latest_available_session(
        db_session,
        OpenWeekdayMarket(),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        occurred_at=after_market_close,
    )
    analysis = await claim_next_onboarding_job(
        db_session,
        occurred_at=after_market_close,
    )
    assert analysis is not None
    await persist_analysis(db_session, instrument.id, date(2026, 7, 27))
    await complete_onboarding_job(
        db_session,
        analysis.job_id,
        occurred_at=after_market_close,
    )
    repeated = await schedule_latest_available_session(
        db_session,
        OpenWeekdayMarket(),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        occurred_at=after_market_close,
    )

    assert first.target_session == date(2026, 7, 27)
    assert first.enqueued_count == 1
    assert repeated.enqueued_count == 0
    assert repeated.skipped_completed_count == 1


@pytest.mark.anyio
async def test_startup_does_not_regress_below_stored_benchmark_session(
    db_session: AsyncSession,
) -> None:
    stored_target = date(2026, 7, 27)
    benchmark = MarketBenchmark(
        code="NIFTY_500",
        name="Nifty 500",
        provider="UPSTOX",
        instrument_key="NSE_INDEX|Nifty 500",
        source_fetched_at=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
    )
    db_session.add(benchmark)
    await db_session.flush()
    db_session.add(
        BenchmarkDailyCandle(
            benchmark_id=benchmark.id,
            trading_date=stored_target,
            open_price=Decimal("100"),
            high_price=Decimal("101"),
            low_price=Decimal("99"),
            close_price=Decimal("100"),
            volume=1000,
            open_interest=0,
            source="UPSTOX_INTRADAY",
            source_timestamp=datetime(2026, 7, 27, 10, 0, tzinfo=UTC),
            fetched_at=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()

    result = await schedule_latest_available_session(
        db_session,
        OpenWeekdayMarket(available_session=TARGET),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        occurred_at=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
    )

    assert result.target_session == stored_target


@pytest.mark.anyio
async def test_startup_schedule_retargets_older_pending_work_without_duplication(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session, "CATCHUP")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        TARGET,
        occurred_at=NOW,
    )
    after_market_close = datetime(2026, 7, 27, 11, 0, tzinfo=UTC)

    scheduled = await schedule_latest_available_session(
        db_session,
        OpenWeekdayMarket(),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        occurred_at=after_market_close,
    )
    jobs = list(
        await db_session.scalars(
            select(AnalysisJob).order_by(AnalysisJob.id)
        )
    )
    technical_job = next(
        job
        for job in jobs
        if job.job_type == AnalysisJobType.ONBOARD_INSTRUMENT
    )
    fundamental_job = next(
        job
        for job in jobs
        if job.job_type == AnalysisJobType.REFRESH_FUNDAMENTALS
    )

    assert scheduled.target_session == date(2026, 7, 27)
    assert scheduled.retargeted_count == 1
    assert scheduled.skipped_active_count == 0
    assert len(jobs) == 2
    assert technical_job.target_session == date(2026, 7, 27)
    assert technical_job.attempt_count == 0
    assert fundamental_job.target_session == TARGET


@pytest.mark.anyio
async def test_startup_schedule_can_finish_after_older_running_work_drains(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session, "RUNNING")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        TARGET,
        occurred_at=NOW,
    )
    onboarding = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert onboarding is not None
    after_market_close = datetime(2026, 7, 27, 11, 0, tzinfo=UTC)

    blocked = await schedule_latest_available_session(
        db_session,
        OpenWeekdayMarket(),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        occurred_at=after_market_close,
    )
    await complete_onboarding_job(db_session, onboarding.job_id, occurred_at=NOW)
    catchup = await schedule_active_watchlist(
        db_session,
        target_session=blocked.target_session,
        occurred_at=after_market_close,
    )

    assert blocked.skipped_active_count == 1
    assert catchup.enqueued_count == 1


@pytest.mark.anyio
async def test_startup_retargets_unpublished_future_pending_job_backward(
    db_session: AsyncSession,
) -> None:
    future_target = date(2026, 7, 27)
    instrument = await persist_instrument(db_session, "FALLBACK")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        future_target,
        occurred_at=datetime(2026, 7, 27, 11, 0, tzinfo=UTC),
    )

    result = await schedule_latest_available_session(
        db_session,
        OpenWeekdayMarket(available_session=TARGET),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        occurred_at=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
    )
    job = await db_session.scalar(
        select(AnalysisJob).where(
            AnalysisJob.job_type == AnalysisJobType.ONBOARD_INSTRUMENT
        )
    )

    assert result.target_session == TARGET
    assert result.retargeted_count == 1
    assert job is not None
    assert job.target_session == TARGET
    assert job.status == AnalysisJobStatus.PENDING


@pytest.mark.anyio
async def test_startup_cancels_future_pending_job_when_available_session_succeeded(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session, "CURRENT")
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        TARGET,
        occurred_at=NOW,
    )
    await discard_pending_fundamental_jobs(db_session)
    onboarding = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert onboarding is not None
    await complete_onboarding_job(db_session, onboarding.job_id, occurred_at=NOW)
    scheduled = await schedule_active_watchlist(
        db_session,
        target_session=TARGET,
        occurred_at=NOW,
    )
    assert scheduled.enqueued_count == 1
    analysis = await claim_next_onboarding_job(db_session, occurred_at=NOW)
    assert analysis is not None
    await persist_analysis(db_session, instrument.id, TARGET)
    await complete_onboarding_job(db_session, analysis.job_id, occurred_at=NOW)
    future = await schedule_active_watchlist(
        db_session,
        target_session=date(2026, 7, 27),
        occurred_at=datetime(2026, 7, 27, 11, 0, tzinfo=UTC),
    )
    assert future.enqueued_count == 1

    result = await schedule_latest_available_session(
        db_session,
        OpenWeekdayMarket(available_session=TARGET),
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        occurred_at=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
    )
    jobs = list(await db_session.scalars(select(AnalysisJob).order_by(AnalysisJob.id)))

    assert result.skipped_completed_count == 1
    assert jobs == []
