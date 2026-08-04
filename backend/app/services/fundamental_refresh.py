from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AnalysisJobType, Instrument, TrackedInstrument
from app.providers.contracts import FundamentalDataProvider
from app.repositories.live_data import get_active_provider_identity
from app.services.fundamentals import persist_fundamentals
from app.services.onboarding_worker import ClaimedOnboardingJob


class FundamentalRefreshError(RuntimeError):
    pass


class FundamentalRefreshHandler:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        provider: FundamentalDataProvider,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._clock = clock

    async def __call__(self, job: ClaimedOnboardingJob) -> None:
        if job.job_type != AnalysisJobType.REFRESH_FUNDAMENTALS:
            raise FundamentalRefreshError("FUNDAMENTAL_JOB_TYPE_REQUIRED")

        async with self._session_factory() as session:
            identity = await get_active_provider_identity(
                session,
                job.instrument_id,
                "UPSTOX",
            )
        if identity is None:
            raise FundamentalRefreshError("ACTIVE_PROVIDER_IDENTITY_REQUIRED")

        bundle = await self._provider.get_fundamentals(isin=identity.isin)
        fetched_at = self._clock()

        async with self._session_factory() as session:
            async with session.begin():
                tracking = await session.scalar(
                    select(TrackedInstrument)
                    .where(TrackedInstrument.id == job.tracked_instrument_id)
                    .with_for_update()
                )
                if tracking is None or not tracking.is_active:
                    raise FundamentalRefreshError("TRACKING_CANCELLED")

                company_id = await session.scalar(
                    select(Instrument.company_id).where(
                        Instrument.id == job.instrument_id
                    )
                )
                if company_id is None:
                    raise FundamentalRefreshError("INSTRUMENT_NOT_FOUND")

                await persist_fundamentals(
                    session,
                    instrument_id=job.instrument_id,
                    company_id=company_id,
                    as_of_date=job.target_session,
                    bundle=bundle,
                    source_fetched_at=fetched_at,
                )
