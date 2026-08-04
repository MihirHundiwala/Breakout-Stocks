from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AnalysisJobType,
    Company,
    FundamentalSnapshot,
    Instrument,
    ProviderInstrumentIdentity,
    TrackedInstrument,
    TrackingOperationalState,
)
from app.providers.contracts import FundamentalBundle
from app.services.fundamental_refresh import FundamentalRefreshHandler
from app.services.onboarding_worker import ClaimedOnboardingJob


class FakeFundamentalProvider:
    def __init__(self) -> None:
        self.requested_isins: list[str] = []

    async def get_fundamentals(self, *, isin: str) -> FundamentalBundle:
        self.requested_isins.append(isin)
        return FundamentalBundle(None, (), (), {}, frozenset({"ratios"}))


@pytest.mark.anyio
async def test_handler_fetches_and_persists_only_fundamentals(
    db_session: AsyncSession,
) -> None:
    occurred_at = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    target_session = date(2026, 7, 27)
    instrument = Instrument(
        company=Company(name="Fundamental Industries Limited"),
        exchange="NSE",
        trading_symbol="FUNDAMENTAL",
    )
    tracking = TrackedInstrument(
        instrument=instrument,
        operational_state=TrackingOperationalState.READY,
        target_session=target_session,
        created_at=occurred_at,
        updated_at=occurred_at,
    )
    db_session.add(tracking)
    await db_session.flush()
    db_session.add(
        ProviderInstrumentIdentity(
            instrument_id=instrument.id,
            provider="UPSTOX",
            instrument_key="NSE_EQ|INE123A01010",
            isin="INE123A01010",
            effective_from=target_session,
            source_fetched_at=occurred_at,
        )
    )
    await db_session.flush()

    provider = FakeFundamentalProvider()
    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    handler = FundamentalRefreshHandler(
        session_factory=factory,
        provider=provider,
        clock=lambda: occurred_at,
    )

    await handler(
        ClaimedOnboardingJob(
            job_id=1,
            tracked_instrument_id=tracking.id,
            instrument_id=instrument.id,
            target_session=target_session,
            attempt_count=1,
            job_type=AnalysisJobType.REFRESH_FUNDAMENTALS,
        )
    )

    snapshot = await db_session.scalar(
        select(FundamentalSnapshot).where(
            FundamentalSnapshot.instrument_id == instrument.id
        )
    )
    await db_session.refresh(tracking)
    assert provider.requested_isins == ["INE123A01010"]
    assert snapshot is not None
    assert snapshot.as_of_date == target_session
    assert tracking.operational_state == TrackingOperationalState.READY
