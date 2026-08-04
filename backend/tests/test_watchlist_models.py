from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    Company,
    Instrument,
    TrackedInstrument,
    TrackingOperationalState,
)


CREATED_AT = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
STARTED_AT = datetime(2026, 7, 25, 10, 1, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 7, 25, 10, 2, tzinfo=UTC)
TARGET_SESSION = date(2026, 7, 24)


def build_instrument() -> Instrument:
    return Instrument(
        company=Company(name="Example Industries Limited"),
        exchange="NSE",
        trading_symbol="EXAMPLE",
    )


def build_tracking(
    instrument: Instrument,
    **overrides: object,
) -> TrackedInstrument:
    values: dict[str, object] = {
        "instrument": instrument,
        "operational_state": TrackingOperationalState.PREPARING,
        "target_session": TARGET_SESSION,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
    values.update(overrides)
    return TrackedInstrument(**values)


def build_job(
    tracking: TrackedInstrument,
    **overrides: object,
) -> AnalysisJob:
    values: dict[str, object] = {
        "tracked_instrument": tracking,
        "job_type": AnalysisJobType.ONBOARD_INSTRUMENT,
        "target_session": TARGET_SESSION,
        "status": AnalysisJobStatus.PENDING,
        "created_at": CREATED_AT,
    }
    values.update(overrides)
    return AnalysisJob(**values)


@pytest.mark.anyio
async def test_tracking_and_pending_job_are_persisted(
    db_session: AsyncSession,
) -> None:
    tracking = build_tracking(build_instrument())
    job = build_job(tracking)

    db_session.add(job)
    await db_session.flush()

    assert tracking.id is not None
    assert job.id is not None
    assert tracking.is_active is True
    assert tracking.instrument.tracked_instrument is tracking
    assert job in tracking.analysis_jobs
    assert job.attempt_count == 0


@pytest.mark.anyio
async def test_instrument_can_have_only_one_tracking_record(
    db_session: AsyncSession,
) -> None:
    instrument = build_instrument()
    db_session.add_all(
        [
            build_tracking(instrument),
            build_tracking(instrument),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_inactive_tracking_requires_deactivation_time(
    db_session: AsyncSession,
) -> None:
    tracking = build_tracking(
        build_instrument(),
        is_active=False,
        deactivated_at=None,
    )
    db_session.add(tracking)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_only_one_active_job_per_tracking_and_type(
    db_session: AsyncSession,
) -> None:
    tracking = build_tracking(build_instrument())
    db_session.add_all(
        [
            build_job(tracking),
            build_job(tracking),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_cancelled_job_allows_same_session_reactivation_job(
    db_session: AsyncSession,
) -> None:
    tracking = build_tracking(build_instrument())
    cancelled_job = build_job(
        tracking,
        status=AnalysisJobStatus.CANCELLED,
        completed_at=COMPLETED_AT,
    )
    db_session.add(cancelled_job)
    await db_session.flush()

    replacement_job = build_job(tracking)
    db_session.add(replacement_job)
    await db_session.flush()

    assert cancelled_job.id is not None
    assert replacement_job.id is not None


@pytest.mark.anyio
async def test_job_rejects_negative_attempt_count(
    db_session: AsyncSession,
) -> None:
    job = build_job(
        build_tracking(build_instrument()),
        attempt_count=-1,
    )
    db_session.add(job)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_succeeded_job_requires_lifecycle_timestamps(
    db_session: AsyncSession,
) -> None:
    job = build_job(
        build_tracking(build_instrument()),
        status=AnalysisJobStatus.SUCCEEDED,
    )
    db_session.add(job)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_failed_job_requires_normalized_error_code(
    db_session: AsyncSession,
) -> None:
    job = build_job(
        build_tracking(build_instrument()),
        status=AnalysisJobStatus.FAILED,
        started_at=STARTED_AT,
        completed_at=COMPLETED_AT,
        error_code="provider_error",
        error_message="Provider request failed",
    )
    db_session.add(job)

    with pytest.raises(IntegrityError):
        await db_session.flush()
