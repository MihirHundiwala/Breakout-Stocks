from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
import re
from typing import Callable, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.technical_analysis import (
    IncompleteCandleHistoryError,
    InsufficientListingHistoryError,
    PersistentCandleGapError,
)
from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    TrackedInstrument,
    TrackingOperationalState,
)
from app.services.job_policy import TERMINAL_TECHNICAL_DATA_ERRORS
from app.providers.errors import ProviderError
from app.repositories.analysis_jobs import (
    get_analysis_job_for_update,
    get_next_pending_analysis_job_for_update,
)


UNEXPECTED_ERROR_CODE = "UNEXPECTED_WORKER_ERROR"
UNEXPECTED_ERROR_MESSAGE = (
    "The onboarding handler raised an unexpected error."
)
ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
TECHNICAL_JOB_TYPES = frozenset(
    {
        AnalysisJobType.ONBOARD_INSTRUMENT,
        AnalysisJobType.ANALYZE_INSTRUMENT,
    }
)


class OnboardingWorkerError(Exception):
    """Base class for expected onboarding worker failures."""


class AnalysisJobNotFoundError(OnboardingWorkerError):
    def __init__(self, job_id: int) -> None:
        super().__init__(f"Analysis job {job_id} was not found.")


class AnalysisJobStateConflictError(OnboardingWorkerError):
    def __init__(
        self,
        job_id: int,
        status: AnalysisJobStatus,
    ) -> None:
        super().__init__(
            f"Analysis job {job_id} cannot be finalized from {status}."
        )


class WorkerRunOutcome(StrEnum):
    NO_JOB = "NO_JOB"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"


@dataclass(frozen=True, slots=True)
class ClaimedOnboardingJob:
    job_id: int
    tracked_instrument_id: int
    instrument_id: int
    target_session: date
    attempt_count: int
    job_type: AnalysisJobType = AnalysisJobType.ANALYZE_INSTRUMENT
    reuse_stored_market_data: bool = False


@dataclass(frozen=True, slots=True)
class FinalizeJobResult:
    job: AnalysisJob
    transitioned: bool
    cancellation_preserved: bool


@dataclass(frozen=True, slots=True)
class WorkerRunResult:
    outcome: WorkerRunOutcome
    job_id: int | None


@dataclass(frozen=True, slots=True)
class StaleRecoveryResult:
    requeued_count: int
    failed_count: int
    cancelled_count: int


class OnboardingJobHandler(Protocol):
    async def __call__(self, job: ClaimedOnboardingJob) -> None: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _event_time(value: datetime | None) -> datetime:
    event_time = value or _utc_now()
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise ValueError("Event timestamps must be timezone-aware.")
    return event_time.astimezone(UTC)


def _normalized_failure(
    error_code: str,
    error_message: str | None,
) -> tuple[str, str | None]:
    normalized_code = error_code.strip().upper()
    if (
        len(normalized_code) > 64
        or ERROR_CODE_PATTERN.fullmatch(normalized_code) is None
    ):
        raise ValueError(
            "Error code must contain at most 64 uppercase letters, "
            "digits, or underscores and start with a letter."
        )

    normalized_message = (
        error_message.strip() if error_message is not None else None
    )
    if normalized_message == "":
        normalized_message = None
    if normalized_message is not None and len(normalized_message) > 512:
        raise ValueError("Error message must contain at most 512 characters.")
    return normalized_code, normalized_message


async def claim_next_onboarding_job(
    session: AsyncSession,
    *,
    occurred_at: datetime | None = None,
) -> ClaimedOnboardingJob | None:
    event_time = _event_time(occurred_at)

    async with session.begin():
        pending = await get_next_pending_analysis_job_for_update(
            session,
            available_at=event_time,
        )
        if pending is None:
            return None

        job = pending.job
        job.status = AnalysisJobStatus.RUNNING
        job.started_at = event_time
        job.attempt_count += 1
        await session.flush()

        return ClaimedOnboardingJob(
            job_id=job.id,
            tracked_instrument_id=job.tracked_instrument_id,
            instrument_id=pending.instrument_id,
            target_session=job.target_session,
            attempt_count=job.attempt_count,
            job_type=job.job_type,
            reuse_stored_market_data=job.reuse_stored_market_data,
        )


async def complete_onboarding_job(
    session: AsyncSession,
    job_id: int,
    *,
    occurred_at: datetime | None = None,
) -> FinalizeJobResult:
    event_time = _event_time(occurred_at)

    async with session.begin():
        job = await get_analysis_job_for_update(session, job_id)
        if job is None:
            raise AnalysisJobNotFoundError(job_id)
        if job.status == AnalysisJobStatus.CANCELLED:
            await session.delete(job)
            return FinalizeJobResult(job, False, True)
        if job.status == AnalysisJobStatus.SUCCEEDED:
            return FinalizeJobResult(job, False, False)
        if job.status != AnalysisJobStatus.RUNNING:
            raise AnalysisJobStateConflictError(job_id, job.status)

        job.status = AnalysisJobStatus.SUCCEEDED
        job.completed_at = event_time
        job.error_code = None
        job.error_message = None
        if job.job_type in TECHNICAL_JOB_TYPES:
            tracking = await session.scalar(
                select(TrackedInstrument)
                .where(TrackedInstrument.id == job.tracked_instrument_id)
                .with_for_update()
            )
            if tracking is not None:
                tracking.terminal_data_error_session = None
                tracking.terminal_data_error_code = None
        await session.flush()
        await session.delete(job)
        return FinalizeJobResult(job, True, False)


async def fail_onboarding_job(
    session: AsyncSession,
    job_id: int,
    error_code: str,
    error_message: str | None,
    *,
    occurred_at: datetime | None = None,
) -> FinalizeJobResult:
    event_time = _event_time(occurred_at)
    normalized_code, normalized_message = _normalized_failure(
        error_code,
        error_message,
    )

    async with session.begin():
        job = await get_analysis_job_for_update(session, job_id)
        if job is None:
            raise AnalysisJobNotFoundError(job_id)
        if job.status == AnalysisJobStatus.CANCELLED:
            await session.delete(job)
            return FinalizeJobResult(job, False, True)
        if job.status == AnalysisJobStatus.FAILED:
            return FinalizeJobResult(job, False, False)
        if job.status != AnalysisJobStatus.RUNNING:
            raise AnalysisJobStateConflictError(job_id, job.status)

        job.status = AnalysisJobStatus.FAILED
        job.completed_at = event_time
        job.error_code = normalized_code
        job.error_message = normalized_message
        tracking = await session.scalar(
            select(TrackedInstrument)
            .where(TrackedInstrument.id == job.tracked_instrument_id)
            .with_for_update()
        )
        if (
            tracking is not None
            and tracking.is_active
            and job.job_type in TECHNICAL_JOB_TYPES
        ):
            tracking.operational_state = TrackingOperationalState.ANALYSIS_FAILED
            tracking.updated_at = event_time
            if normalized_code in TERMINAL_TECHNICAL_DATA_ERRORS:
                tracking.terminal_data_error_session = job.target_session
                tracking.terminal_data_error_code = normalized_code
        await session.flush()
        await session.delete(job)
        return FinalizeJobResult(job, True, False)


async def retry_onboarding_job(
    session: AsyncSession,
    job_id: int,
    *,
    next_attempt_at: datetime,
    occurred_at: datetime | None = None,
) -> FinalizeJobResult:
    event_time = _event_time(occurred_at)
    retry_time = _event_time(next_attempt_at)
    if retry_time <= event_time:
        raise ValueError("next_attempt_at must be after the retry decision time.")

    async with session.begin():
        job = await get_analysis_job_for_update(session, job_id)
        if job is None:
            raise AnalysisJobNotFoundError(job_id)
        if job.status == AnalysisJobStatus.CANCELLED:
            return FinalizeJobResult(job, False, True)
        if job.status != AnalysisJobStatus.RUNNING:
            raise AnalysisJobStateConflictError(job_id, job.status)

        job.status = AnalysisJobStatus.PENDING
        job.started_at = None
        job.completed_at = None
        job.next_attempt_at = retry_time
        job.error_code = None
        job.error_message = None
        await session.flush()
        return FinalizeJobResult(job, True, False)


def _safe_handler_failure(error: Exception) -> tuple[str, str | None, bool]:
    if isinstance(error, ProviderError):
        return error.code, None, error.retryable
    if isinstance(error, InsufficientListingHistoryError):
        return (
            "INSUFFICIENT_LISTING_HISTORY",
            "The stock does not yet have enough complete sessions for analysis.",
            False,
        )
    if isinstance(error, PersistentCandleGapError):
        return (
            "PERSISTENT_CANDLE_GAPS",
            "Upstox omitted one or more internal completed trading sessions after gap filling.",
            False,
        )
    if isinstance(error, IncompleteCandleHistoryError):
        return (
            "INCOMPLETE_CANDLE_HISTORY",
            "The completed-session candle window is incomplete.",
            True,
        )
    return UNEXPECTED_ERROR_CODE, UNEXPECTED_ERROR_MESSAGE, False


async def recover_stale_onboarding_jobs(
    session: AsyncSession,
    *,
    stale_before: datetime,
    occurred_at: datetime | None = None,
    maximum_attempts: int = 3,
    retry_delay_seconds: int = 60,
) -> StaleRecoveryResult:
    event_time = _event_time(occurred_at)
    stale_time = _event_time(stale_before)
    if stale_time >= event_time:
        raise ValueError("stale_before must be earlier than occurred_at.")
    if maximum_attempts < 1 or retry_delay_seconds < 1:
        raise ValueError("Recovery limits must be positive.")

    requeued = failed = cancelled = 0
    async with session.begin():
        rows = (
            await session.execute(
                select(AnalysisJob, TrackedInstrument)
                .join(
                    TrackedInstrument,
                    TrackedInstrument.id == AnalysisJob.tracked_instrument_id,
                )
                .where(
                    AnalysisJob.status == AnalysisJobStatus.RUNNING,
                    AnalysisJob.started_at < stale_time,
                )
                .order_by(AnalysisJob.started_at, AnalysisJob.id)
                .with_for_update(
                    of=(AnalysisJob, TrackedInstrument),
                    skip_locked=True,
                )
            )
        ).all()
        for job, tracking in rows:
            if not tracking.is_active:
                await session.delete(job)
                cancelled += 1
            elif job.attempt_count < maximum_attempts:
                job.status = AnalysisJobStatus.PENDING
                job.started_at = None
                job.completed_at = None
                job.next_attempt_at = event_time + timedelta(seconds=retry_delay_seconds)
                job.error_code = None
                job.error_message = None
                requeued += 1
            else:
                job.status = AnalysisJobStatus.FAILED
                job.completed_at = event_time
                job.error_code = "STALE_JOB_TIMEOUT"
                job.error_message = "The worker stopped before the job completed."
                if job.job_type in TECHNICAL_JOB_TYPES:
                    tracking.operational_state = (
                        TrackingOperationalState.ANALYSIS_FAILED
                    )
                    tracking.updated_at = event_time
                await session.delete(job)
                failed += 1
        await session.flush()
    return StaleRecoveryResult(requeued, failed, cancelled)


async def process_one_onboarding_job(
    session_factory: async_sessionmaker[AsyncSession],
    handler: OnboardingJobHandler,
    *,
    clock: Callable[[], datetime] = _utc_now,
    maximum_attempts: int = 3,
    retry_base_seconds: int = 60,
) -> WorkerRunResult:
    if maximum_attempts < 1:
        raise ValueError("maximum_attempts must be at least 1.")
    if retry_base_seconds < 1:
        raise ValueError("retry_base_seconds must be at least 1.")
    async with session_factory() as session:
        claimed = await claim_next_onboarding_job(
            session,
            occurred_at=clock(),
        )
    if claimed is None:
        return WorkerRunResult(WorkerRunOutcome.NO_JOB, None)

    try:
        await handler(claimed)
    except Exception as error:
        error_code, error_message, retryable = _safe_handler_failure(error)
        decision_time = clock()
        if retryable and claimed.attempt_count < maximum_attempts:
            delay_seconds = min(
                retry_base_seconds * (2 ** (claimed.attempt_count - 1)),
                15 * 60,
            )
            async with session_factory() as session:
                try:
                    finalization = await retry_onboarding_job(
                        session,
                        claimed.job_id,
                        next_attempt_at=(
                            decision_time + timedelta(seconds=delay_seconds)
                        ),
                        occurred_at=decision_time,
                    )
                except AnalysisJobNotFoundError:
                    return WorkerRunResult(
                        WorkerRunOutcome.CANCELLED,
                        claimed.job_id,
                    )
            outcome = (
                WorkerRunOutcome.CANCELLED
                if finalization.cancellation_preserved
                else WorkerRunOutcome.RETRY_SCHEDULED
            )
            return WorkerRunResult(outcome, claimed.job_id)

        async with session_factory() as session:
            try:
                finalization = await fail_onboarding_job(
                    session,
                    claimed.job_id,
                    error_code,
                    error_message,
                    occurred_at=decision_time,
                )
            except AnalysisJobNotFoundError:
                return WorkerRunResult(
                    WorkerRunOutcome.CANCELLED,
                    claimed.job_id,
                )
        outcome = (
            WorkerRunOutcome.CANCELLED
            if finalization.cancellation_preserved
            else WorkerRunOutcome.FAILED
        )
        return WorkerRunResult(outcome, claimed.job_id)

    async with session_factory() as session:
        try:
            finalization = await complete_onboarding_job(
                session,
                claimed.job_id,
                occurred_at=clock(),
            )
        except AnalysisJobNotFoundError:
            return WorkerRunResult(
                WorkerRunOutcome.CANCELLED,
                claimed.job_id,
            )
    outcome = (
        WorkerRunOutcome.CANCELLED
        if finalization.cancellation_preserved
        else WorkerRunOutcome.SUCCEEDED
    )
    return WorkerRunResult(outcome, claimed.job_id)
