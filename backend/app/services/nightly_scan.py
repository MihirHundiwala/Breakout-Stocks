from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    AnalysisSnapshot,
    BenchmarkDailyCandle,
    MarketBenchmark,
    TrackedInstrument,
    TrackingOperationalState,
)
from app.providers.contracts import AnalysisMarketDataProvider
from app.services.job_policy import TERMINAL_TECHNICAL_DATA_ERRORS
from app.services.market_sessions import resolve_latest_available_nse_session


@dataclass(frozen=True, slots=True)
class NightlyScheduleResult:
    target_session: date
    enqueued_count: int
    retargeted_count: int
    skipped_active_count: int
    skipped_completed_count: int
    skipped_terminal_count: int


async def schedule_worker_startup(
    session: AsyncSession,
    provider: AnalysisMarketDataProvider,
    *,
    enabled: bool,
    benchmark_instrument_key: str,
    occurred_at: datetime | None = None,
) -> NightlyScheduleResult | None:
    if not enabled:
        return None
    return await schedule_latest_available_session(
        session,
        provider,
        benchmark_instrument_key=benchmark_instrument_key,
        occurred_at=occurred_at,
    )


async def schedule_latest_available_session(
    session: AsyncSession,
    provider: AnalysisMarketDataProvider,
    *,
    benchmark_instrument_key: str,
    occurred_at: datetime | None = None,
) -> NightlyScheduleResult:
    event_time = occurred_at or datetime.now(UTC)
    target_session = await resolve_latest_known_session(
        session,
        provider,
        benchmark_instrument_key=benchmark_instrument_key,
        now=event_time,
    )
    return await schedule_active_watchlist(
        session,
        target_session=target_session,
        occurred_at=event_time,
    )


async def resolve_latest_known_session(
    session: AsyncSession,
    provider: AnalysisMarketDataProvider,
    *,
    benchmark_instrument_key: str,
    now: datetime,
) -> date:
    provider_session = await resolve_latest_available_nse_session(
        provider,
        benchmark_instrument_key=benchmark_instrument_key,
        now=now,
    )
    async with session.begin():
        stored_session = await session.scalar(
            select(func.max(BenchmarkDailyCandle.trading_date))
            .join(MarketBenchmark)
            .where(MarketBenchmark.code == "NIFTY_500")
        )
    return max(provider_session, stored_session or provider_session)


async def schedule_active_watchlist(
    session: AsyncSession,
    *,
    target_session: date,
    force_reanalysis: bool = False,
    reuse_stored_market_data: bool = False,
    occurred_at: datetime | None = None,
) -> NightlyScheduleResult:
    event_time = occurred_at or datetime.now(UTC)
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise ValueError("Event timestamps must be timezone-aware.")
    event_time = event_time.astimezone(UTC)

    enqueued = retargeted = active = completed = terminal = 0
    async with session.begin():
        trackings = list(
            await session.scalars(
                select(TrackedInstrument)
                .where(TrackedInstrument.is_active.is_(True))
                .order_by(TrackedInstrument.id)
                .with_for_update(skip_locked=True)
            )
        )
        for tracking in trackings:
            active_job = await session.scalar(
                select(AnalysisJob)
                .where(
                    AnalysisJob.tracked_instrument_id == tracking.id,
                    AnalysisJob.job_type.in_(
                        (
                            AnalysisJobType.ONBOARD_INSTRUMENT,
                            AnalysisJobType.ANALYZE_INSTRUMENT,
                        )
                    ),
                    AnalysisJob.status.in_(
                        (AnalysisJobStatus.PENDING, AnalysisJobStatus.RUNNING)
                    ),
                )
                .order_by(AnalysisJob.created_at, AnalysisJob.id)
                .with_for_update()
            )
            completed_analysis_id = await session.scalar(
                select(AnalysisSnapshot.id)
                .where(
                    AnalysisSnapshot.instrument_id == tracking.instrument_id,
                    AnalysisSnapshot.analysis_date == target_session,
                )
                .limit(1)
            )
            already_completed = completed_analysis_id is not None
            already_terminal = (
                tracking.terminal_data_error_session == target_session
                and tracking.terminal_data_error_code
                in TERMINAL_TECHNICAL_DATA_ERRORS
            )
            if (already_completed and not force_reanalysis) or already_terminal:
                if (
                    active_job is not None
                    and active_job.status == AnalysisJobStatus.RUNNING
                ):
                    active += 1
                    continue
                if (
                    active_job is not None
                    and active_job.status == AnalysisJobStatus.PENDING
                ):
                    await session.delete(active_job)
                tracking.target_session = target_session
                tracking.operational_state = (
                    TrackingOperationalState.ANALYSIS_FAILED
                    if already_terminal
                    else TrackingOperationalState.READY
                )
                tracking.updated_at = event_time
                if already_terminal:
                    terminal += 1
                else:
                    completed += 1
                continue

            if (
                active_job is not None
                and active_job.status == AnalysisJobStatus.PENDING
                and active_job.target_session != target_session
            ):
                active_job.target_session = target_session
                active_job.attempt_count = 0
                active_job.next_attempt_at = event_time
                active_job.reuse_stored_market_data = reuse_stored_market_data
                tracking.terminal_data_error_session = None
                tracking.terminal_data_error_code = None
                tracking.target_session = target_session
                tracking.operational_state = TrackingOperationalState.PREPARING
                tracking.updated_at = event_time
                retargeted += 1
                continue
            if active_job is not None:
                active += 1
                continue

            session.add(
                AnalysisJob(
                    tracked_instrument_id=tracking.id,
                    job_type=AnalysisJobType.ANALYZE_INSTRUMENT,
                    target_session=target_session,
                    status=AnalysisJobStatus.PENDING,
                    attempt_count=0,
                    reuse_stored_market_data=reuse_stored_market_data,
                    created_at=event_time,
                    next_attempt_at=event_time,
                )
            )
            tracking.target_session = target_session
            tracking.operational_state = TrackingOperationalState.PREPARING
            tracking.terminal_data_error_session = None
            tracking.terminal_data_error_code = None
            tracking.updated_at = event_time
            enqueued += 1
        await session.flush()

    return NightlyScheduleResult(
        target_session,
        enqueued,
        retargeted,
        active,
        completed,
        terminal,
    )


async def schedule_fundamental_refresh(
    session: AsyncSession,
    *,
    target_session: date,
    occurred_at: datetime | None = None,
) -> NightlyScheduleResult:
    event_time = occurred_at or datetime.now(UTC)
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise ValueError("Event timestamps must be timezone-aware.")
    event_time = event_time.astimezone(UTC)

    enqueued = retargeted = active = 0
    async with session.begin():
        trackings = list(
            await session.scalars(
                select(TrackedInstrument)
                .where(TrackedInstrument.is_active.is_(True))
                .order_by(TrackedInstrument.id)
                .with_for_update(skip_locked=True)
            )
        )
        for tracking in trackings:
            active_job = await session.scalar(
                select(AnalysisJob)
                .where(
                    AnalysisJob.tracked_instrument_id == tracking.id,
                    AnalysisJob.job_type
                    == AnalysisJobType.REFRESH_FUNDAMENTALS,
                    AnalysisJob.status.in_(
                        (AnalysisJobStatus.PENDING, AnalysisJobStatus.RUNNING)
                    ),
                )
                .order_by(AnalysisJob.created_at, AnalysisJob.id)
                .with_for_update()
            )
            if active_job is not None:
                if (
                    active_job.status == AnalysisJobStatus.PENDING
                    and active_job.target_session != target_session
                ):
                    active_job.target_session = target_session
                    active_job.attempt_count = 0
                    active_job.next_attempt_at = event_time
                    retargeted += 1
                else:
                    active += 1
                continue

            session.add(
                AnalysisJob(
                    tracked_instrument_id=tracking.id,
                    job_type=AnalysisJobType.REFRESH_FUNDAMENTALS,
                    target_session=target_session,
                    status=AnalysisJobStatus.PENDING,
                    attempt_count=0,
                    reuse_stored_market_data=False,
                    created_at=event_time,
                    next_attempt_at=event_time,
                )
            )
            enqueued += 1
        await session.flush()

    return NightlyScheduleResult(
        target_session=target_session,
        enqueued_count=enqueued,
        retargeted_count=retargeted,
        skipped_active_count=active,
        skipped_completed_count=0,
        skipped_terminal_count=0,
    )
