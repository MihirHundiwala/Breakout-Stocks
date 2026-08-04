from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    TrackedInstrument,
)


@dataclass(frozen=True, slots=True)
class PendingAnalysisJob:
    job: AnalysisJob
    instrument_id: int


async def get_next_pending_analysis_job_for_update(
    session: AsyncSession,
    *,
    available_at: datetime,
) -> PendingAnalysisJob | None:
    statement = (
        select(AnalysisJob, TrackedInstrument.instrument_id)
        .join(
            TrackedInstrument,
            TrackedInstrument.id
            == AnalysisJob.tracked_instrument_id,
        )
        .where(
            AnalysisJob.job_type.in_(
                (
                    AnalysisJobType.ONBOARD_INSTRUMENT,
                    AnalysisJobType.ANALYZE_INSTRUMENT,
                    AnalysisJobType.REFRESH_FUNDAMENTALS,
                )
            ),
            AnalysisJob.status == AnalysisJobStatus.PENDING,
            AnalysisJob.next_attempt_at <= available_at,
            TrackedInstrument.is_active.is_(True),
        )
        .order_by(
            AnalysisJob.next_attempt_at,
            AnalysisJob.created_at,
            AnalysisJob.id,
        )
        .limit(1)
        .with_for_update(
            of=(AnalysisJob, TrackedInstrument),
            skip_locked=True,
        )
    )
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        return None
    return PendingAnalysisJob(
        job=row[0],
        instrument_id=row[1],
    )


async def get_analysis_job_for_update(
    session: AsyncSession,
    job_id: int,
) -> AnalysisJob | None:
    statement = (
        select(AnalysisJob)
        .where(AnalysisJob.id == job_id)
        .with_for_update()
    )
    return await session.scalar(statement)
