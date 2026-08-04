from datetime import UTC, date, datetime, timedelta
from typing import Callable

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import delete, func, select

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    Company,
    Instrument,
    TrackedInstrument,
    TrackingOperationalState,
)
from app.providers.errors import ProviderError
from app.domain.technical_analysis import (
    IncompleteCandleHistoryError,
    InsufficientListingHistoryError,
    PersistentCandleGapError,
)
from app.services.onboarding_worker import (
    AnalysisJobStateConflictError,
    ClaimedOnboardingJob,
    WorkerRunOutcome,
    claim_next_onboarding_job,
    complete_onboarding_job,
    fail_onboarding_job,
    process_one_onboarding_job,
    recover_stale_onboarding_jobs,
)
from app.services.watchlist import (
    add_or_reactivate_instrument,
    deactivate_instrument,
)


CREATED_AT = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
CLAIMED_AT = datetime(2026, 7, 25, 10, 5, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 7, 25, 10, 10, tzinfo=UTC)
TARGET_SESSION = date(2026, 7, 24)


async def persist_instrument(
    session: AsyncSession,
    symbol: str = "EXAMPLE",
) -> Instrument:
    instrument = Instrument(
        company=Company(name=f"{symbol} Industries Limited"),
        exchange="NSE",
        trading_symbol=symbol,
    )
    session.add(instrument)
    await session.commit()
    return instrument


async def add_pending_job(
    session: AsyncSession,
    symbol: str = "EXAMPLE",
    *,
    occurred_at: datetime = CREATED_AT,
):
    instrument = await persist_instrument(session, symbol)
    result = await add_or_reactivate_instrument(
        session,
        instrument.id,
        TARGET_SESSION,
        occurred_at=occurred_at,
    )
    assert result.analysis_job is not None
    # These worker-state tests intentionally exercise one synthetic job at a
    # time. New watchlist tracking also queues an independent fundamental job,
    # which is covered by the watchlist/nightly integration tests.
    await session.execute(
        delete(AnalysisJob).where(
            AnalysisJob.tracked_instrument_id
            == result.analysis_job.tracked_instrument_id,
            AnalysisJob.job_type == AnalysisJobType.REFRESH_FUNDAMENTALS,
        )
    )
    await session.commit()
    return instrument, result.analysis_job


def build_worker_session_factory(
    db_session: AsyncSession,
) -> async_sessionmaker[AsyncSession]:
    assert db_session.bind is not None
    return async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


def worker_clock() -> Callable[[], datetime]:
    timestamps = iter([CLAIMED_AT, COMPLETED_AT])
    return lambda: next(timestamps)


@pytest.mark.anyio
async def test_claim_returns_none_when_no_job_is_pending(
    db_session: AsyncSession,
) -> None:
    claimed = await claim_next_onboarding_job(
        db_session,
        occurred_at=CLAIMED_AT,
    )

    assert claimed is None


@pytest.mark.anyio
async def test_claim_uses_oldest_pending_job_and_increments_attempt(
    db_session: AsyncSession,
) -> None:
    first_instrument, first_job = await add_pending_job(
        db_session,
        "FIRST",
    )
    _second_instrument, second_job = await add_pending_job(
        db_session,
        "SECOND",
        occurred_at=CREATED_AT + timedelta(minutes=1),
    )

    claimed = await claim_next_onboarding_job(
        db_session,
        occurred_at=CLAIMED_AT,
    )
    next_claimed = await claim_next_onboarding_job(
        db_session,
        occurred_at=CLAIMED_AT + timedelta(seconds=1),
    )

    assert claimed is not None
    assert claimed.job_id == first_job.id
    assert claimed.instrument_id == first_instrument.id
    assert claimed.target_session == TARGET_SESSION
    assert claimed.attempt_count == 1
    assert first_job.status == AnalysisJobStatus.RUNNING
    assert first_job.started_at == CLAIMED_AT
    assert next_claimed is not None
    assert next_claimed.job_id == second_job.id


@pytest.mark.anyio
async def test_successful_handler_completes_the_job(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)
    job_id = job.id
    handled: list[ClaimedOnboardingJob] = []

    async def successful_handler(claimed: ClaimedOnboardingJob) -> None:
        handled.append(claimed)

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        successful_handler,
        clock=worker_clock(),
    )
    stored_job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob).where(AnalysisJob.id == job_id)
    )

    assert result.outcome == WorkerRunOutcome.SUCCEEDED
    assert result.job_id == job_id
    assert [claimed.job_id for claimed in handled] == [job_id]
    assert stored_job_count == 0


@pytest.mark.anyio
async def test_unexpected_handler_error_fails_without_storing_exception(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)
    job_id = job.id
    tracking_id = job.tracked_instrument_id

    async def failing_handler(_claimed: ClaimedOnboardingJob) -> None:
        raise RuntimeError("synthetic provider token must not be stored")

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        failing_handler,
        clock=worker_clock(),
    )
    stored_job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob).where(AnalysisJob.id == job_id)
    )
    tracking = await db_session.get(TrackedInstrument, tracking_id)
    assert tracking is not None
    await db_session.refresh(tracking)

    assert result.outcome == WorkerRunOutcome.FAILED
    assert stored_job_count == 0
    assert tracking.operational_state == TrackingOperationalState.ANALYSIS_FAILED
    assert tracking.terminal_data_error_code is None


@pytest.mark.anyio
@pytest.mark.parametrize("raise_after_cancellation", [False, True])
async def test_admin_removal_during_handler_preserves_cancellation(
    db_session: AsyncSession,
    raise_after_cancellation: bool,
) -> None:
    instrument, job = await add_pending_job(db_session)

    async def cancelling_handler(_claimed: ClaimedOnboardingJob) -> None:
        await deactivate_instrument(
            db_session,
            instrument.id,
            occurred_at=COMPLETED_AT,
        )
        if raise_after_cancellation:
            raise RuntimeError("cancelled handler stopped")

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        cancelling_handler,
        clock=worker_clock(),
    )
    stored_job = await db_session.get(AnalysisJob, job.id)

    assert result.outcome == WorkerRunOutcome.CANCELLED
    assert stored_job is None


@pytest.mark.anyio
async def test_pending_job_cannot_be_completed_without_claim(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)
    with pytest.raises(AnalysisJobStateConflictError):
        await complete_onboarding_job(
            db_session,
            job.id,
            occurred_at=COMPLETED_AT,
        )


@pytest.mark.anyio
async def test_failure_metadata_is_normalized(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)
    await claim_next_onboarding_job(
        db_session,
        occurred_at=CLAIMED_AT,
    )

    result = await fail_onboarding_job(
        db_session,
        job.id,
        " provider_error ",
        " Provider request failed ",
        occurred_at=COMPLETED_AT,
    )

    assert result.transitioned is True
    assert result.job.status == AnalysisJobStatus.FAILED
    assert result.job.error_code == "PROVIDER_ERROR"
    assert result.job.error_message == "Provider request failed"
    assert await db_session.get(AnalysisJob, job.id) is None


@pytest.mark.anyio
async def test_claim_rejects_naive_event_timestamp(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        await claim_next_onboarding_job(
            db_session,
            occurred_at=datetime(2026, 7, 25, 10, 0),
        )


@pytest.mark.anyio
async def test_retryable_provider_failure_is_scheduled_with_backoff(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)

    async def unavailable(_claimed: ClaimedOnboardingJob) -> None:
        raise ProviderError(code="UPSTOX_TIMEOUT", retryable=True)

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        unavailable,
        clock=worker_clock(),
        maximum_attempts=3,
        retry_base_seconds=60,
    )
    await db_session.refresh(job)

    assert result.outcome == WorkerRunOutcome.RETRY_SCHEDULED
    assert job.status == AnalysisJobStatus.PENDING
    assert job.attempt_count == 1
    assert job.started_at is None
    assert job.next_attempt_at == COMPLETED_AT + timedelta(seconds=60)
    async with build_worker_session_factory(db_session)() as claim_session:
        assert await claim_next_onboarding_job(
            claim_session,
            occurred_at=COMPLETED_AT + timedelta(seconds=59),
        ) is None


@pytest.mark.anyio
async def test_incomplete_candle_gap_is_retryable(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)

    async def incomplete(_claimed: ClaimedOnboardingJob) -> None:
        raise IncompleteCandleHistoryError("synthetic internal gap")

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        incomplete,
        clock=worker_clock(),
        maximum_attempts=3,
    )
    await db_session.refresh(job)

    assert result.outcome == WorkerRunOutcome.RETRY_SCHEDULED
    assert job.status == AnalysisJobStatus.PENDING
    assert job.attempt_count == 1


@pytest.mark.anyio
async def test_insufficient_listing_history_fails_without_retry(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)
    job_id = job.id
    tracking_id = job.tracked_instrument_id

    async def insufficient(_claimed: ClaimedOnboardingJob) -> None:
        raise InsufficientListingHistoryError("synthetic recent listing")

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        insufficient,
        clock=worker_clock(),
        maximum_attempts=3,
    )
    tracking = await db_session.get(TrackedInstrument, tracking_id)
    assert tracking is not None
    await db_session.refresh(tracking)
    stored_job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob).where(AnalysisJob.id == job_id)
    )

    assert result.outcome == WorkerRunOutcome.FAILED
    assert stored_job_count == 0
    assert tracking.terminal_data_error_session == TARGET_SESSION
    assert tracking.terminal_data_error_code == "INSUFFICIENT_LISTING_HISTORY"


@pytest.mark.anyio
async def test_persistent_candle_gap_fails_without_retry(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)
    job_id = job.id
    tracking_id = job.tracked_instrument_id

    async def persistent_gap(_claimed: ClaimedOnboardingJob) -> None:
        raise PersistentCandleGapError("synthetic provider-confirmed gap")

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        persistent_gap,
        clock=worker_clock(),
        maximum_attempts=3,
    )
    tracking = await db_session.get(TrackedInstrument, tracking_id)
    assert tracking is not None
    await db_session.refresh(tracking)
    stored_job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob).where(AnalysisJob.id == job_id)
    )

    assert result.outcome == WorkerRunOutcome.FAILED
    assert stored_job_count == 0
    assert tracking.terminal_data_error_session == TARGET_SESSION
    assert tracking.terminal_data_error_code == "PERSISTENT_CANDLE_GAPS"


@pytest.mark.anyio
async def test_retry_limit_sets_terminal_operational_failure(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)
    job_id = job.id
    tracking_id = job.tracked_instrument_id

    async def unavailable(_claimed: ClaimedOnboardingJob) -> None:
        raise ProviderError(code="UPSTOX_RATE_LIMITED", retryable=True)

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        unavailable,
        clock=worker_clock(),
        maximum_attempts=1,
    )
    tracking = await db_session.scalar(
        select(TrackedInstrument).where(TrackedInstrument.id == tracking_id)
    )
    assert tracking is not None
    await db_session.refresh(tracking)
    stored_job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob).where(AnalysisJob.id == job_id)
    )

    assert result.outcome == WorkerRunOutcome.FAILED
    assert stored_job_count == 0
    assert tracking.operational_state == TrackingOperationalState.ANALYSIS_FAILED
    assert tracking.terminal_data_error_code is None


@pytest.mark.anyio
async def test_fundamental_failure_does_not_replace_technical_state(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session, "FUNDFAIL")
    job_id = job.id
    tracking = await db_session.scalar(
        select(TrackedInstrument).where(
            TrackedInstrument.id == job.tracked_instrument_id
        )
    )
    assert tracking is not None
    job.job_type = AnalysisJobType.REFRESH_FUNDAMENTALS
    tracking.operational_state = TrackingOperationalState.READY
    await db_session.commit()

    async def unavailable(_claimed: ClaimedOnboardingJob) -> None:
        raise ProviderError(code="UPSTOX_RATE_LIMITED", retryable=True)

    result = await process_one_onboarding_job(
        build_worker_session_factory(db_session),
        unavailable,
        clock=worker_clock(),
        maximum_attempts=1,
    )
    await db_session.refresh(tracking)
    stored_job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob).where(AnalysisJob.id == job_id)
    )

    assert result.outcome == WorkerRunOutcome.FAILED
    assert stored_job_count == 0
    assert tracking.operational_state == TrackingOperationalState.READY


@pytest.mark.anyio
async def test_instrument_purged_during_processing_is_cancelled(
    db_session: AsyncSession,
) -> None:
    instrument, job = await add_pending_job(db_session, "PURGED")
    factory = build_worker_session_factory(db_session)

    async def purge_while_running(_claimed: ClaimedOnboardingJob) -> None:
        async with factory() as session:
            async with session.begin():
                await session.execute(
                    delete(Instrument).where(Instrument.id == instrument.id)
                )

    result = await process_one_onboarding_job(
        factory,
        purge_while_running,
        clock=worker_clock(),
    )

    assert result.outcome == WorkerRunOutcome.CANCELLED
    assert result.job_id == job.id
    assert await db_session.scalar(
        select(func.count())
        .select_from(Instrument)
        .where(Instrument.id == instrument.id)
    ) == 0


@pytest.mark.anyio
async def test_stale_running_job_is_requeued_after_worker_crash(
    db_session: AsyncSession,
) -> None:
    _instrument, job = await add_pending_job(db_session)
    await claim_next_onboarding_job(db_session, occurred_at=CLAIMED_AT)

    recovered = await recover_stale_onboarding_jobs(
        db_session,
        stale_before=CLAIMED_AT + timedelta(minutes=1),
        occurred_at=COMPLETED_AT,
        maximum_attempts=3,
        retry_delay_seconds=30,
    )

    assert recovered.requeued_count == 1
    assert recovered.failed_count == 0
    assert job.status == AnalysisJobStatus.PENDING
    assert job.started_at is None
    assert job.next_attempt_at == COMPLETED_AT + timedelta(seconds=30)
