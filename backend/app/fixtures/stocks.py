from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AnalysisSnapshot,
    Company,
    FundamentalCoverageStatus,
    Instrument,
    TechnicalStatus,
    TrackedInstrument,
    TrackingOperationalState,
    UserWatchlistItem,
)


FIXTURE_ANALYSIS_DATE = date(2026, 7, 22)
FIXTURE_SOURCE_FETCHED_AT = datetime(
    2026,
    7,
    22,
    12,
    0,
    tzinfo=UTC,
)
FIXTURE_ALGORITHM_VERSION = "fixture-v1"
FIXTURE_CANDLE_REVISION = "synthetic-v1"


@dataclass(frozen=True)
class StockFixture:
    company_name: str
    trading_symbol: str
    technical_status: TechnicalStatus
    fundamental_coverage: FundamentalCoverageStatus
    close_price: Decimal
    previous_close_price: Decimal
    pivot_price: Decimal | None
    breakout_confirmed_on: date | None


@dataclass(frozen=True)
class FixtureSeedSummary:
    companies_created: int
    instruments_created: int
    snapshots_created: int
    trackings_created: int
    memberships_created: int


STOCK_FIXTURES = (
    StockFixture(
        company_name="Aurora Engineering Limited",
        trading_symbol="AURORA",
        technical_status=TechnicalStatus.SETUP_FOUND,
        fundamental_coverage=FundamentalCoverageStatus.COMPLETE,
        close_price=Decimal("512.8000"),
        previous_close_price=Decimal("506.2500"),
        pivot_price=None,
        breakout_confirmed_on=None,
    ),
    StockFixture(
        company_name="Nexus Consumer Products Limited",
        trading_symbol="NEXUS",
        technical_status=TechnicalStatus.SETUP_FOUND,
        fundamental_coverage=FundamentalCoverageStatus.PARTIAL,
        close_price=Decimal("847.3000"),
        previous_close_price=Decimal("840.1000"),
        pivot_price=None,
        breakout_confirmed_on=None,
    ),
    StockFixture(
        company_name="Horizon Financial Services Limited",
        trading_symbol="HORIZON",
        technical_status=TechnicalStatus.NO_SETUP,
        fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
        close_price=Decimal("231.4000"),
        previous_close_price=Decimal("233.1500"),
        pivot_price=None,
        breakout_confirmed_on=None,
    ),
)


async def seed_stock_fixtures(
    session: AsyncSession,
    *,
    owner_user_id: int | None = None,
) -> FixtureSeedSummary:
    reactivation_time = datetime.now(UTC)
    companies_created = 0
    instruments_created = 0
    snapshots_created = 0
    trackings_created = 0
    memberships_created = 0

    for fixture in STOCK_FIXTURES:
        instrument = await session.scalar(
            select(Instrument)
            .options(selectinload(Instrument.company))
            .where(
                Instrument.exchange == "NSE",
                Instrument.trading_symbol == fixture.trading_symbol,
            )
        )

        if instrument is None:
            company = Company(name=fixture.company_name)
            instrument = Instrument(
                company=company,
                exchange="NSE",
                trading_symbol=fixture.trading_symbol,
            )
            session.add(instrument)
            await session.flush()
            companies_created += 1
            instruments_created += 1
        elif instrument.company.name != fixture.company_name:
            raise ValueError(
                "Fixture instrument identity already belongs to "
                "a different company."
            )

        snapshot_exists = await session.scalar(
            select(AnalysisSnapshot.id).where(
                AnalysisSnapshot.instrument_id == instrument.id,
                AnalysisSnapshot.analysis_date
                == FIXTURE_ANALYSIS_DATE,
                AnalysisSnapshot.algorithm_version
                == FIXTURE_ALGORITHM_VERSION,
                AnalysisSnapshot.candle_revision
                == FIXTURE_CANDLE_REVISION,
            )
        )

        if snapshot_exists is None:
            session.add(
                AnalysisSnapshot(
                    instrument=instrument,
                    analysis_date=FIXTURE_ANALYSIS_DATE,
                    technical_status=fixture.technical_status,
                    fundamental_coverage=(
                        fixture.fundamental_coverage
                    ),
                    close_price=fixture.close_price,
                    previous_close_price=(
                        fixture.previous_close_price
                    ),
                    pivot_price=fixture.pivot_price,
                    breakout_confirmed_on=(
                        fixture.breakout_confirmed_on
                    ),
                    source="FIXTURE",
                    source_fetched_at=FIXTURE_SOURCE_FETCHED_AT,
                    algorithm_version=FIXTURE_ALGORITHM_VERSION,
                    candle_revision=FIXTURE_CANDLE_REVISION,
                )
            )
            snapshots_created += 1

        if owner_user_id is not None:
            tracking = await session.scalar(
                select(TrackedInstrument).where(
                    TrackedInstrument.instrument_id == instrument.id
                )
            )
            if tracking is None:
                tracking = TrackedInstrument(
                    instrument_id=instrument.id,
                    is_active=True,
                    operational_state=TrackingOperationalState.READY,
                    target_session=FIXTURE_ANALYSIS_DATE,
                    created_at=FIXTURE_SOURCE_FETCHED_AT,
                    updated_at=FIXTURE_SOURCE_FETCHED_AT,
                )
                session.add(tracking)
                trackings_created += 1
            elif not tracking.is_active:
                tracking.is_active = True
                tracking.deactivated_at = None
                tracking.reactivated_at = reactivation_time
                tracking.operational_state = TrackingOperationalState.READY
                tracking.target_session = FIXTURE_ANALYSIS_DATE
                tracking.updated_at = reactivation_time

            membership = await session.scalar(
                select(UserWatchlistItem).where(
                    UserWatchlistItem.user_id == owner_user_id,
                    UserWatchlistItem.instrument_id == instrument.id,
                )
            )
            if membership is None:
                session.add(
                    UserWatchlistItem(
                        user_id=owner_user_id,
                        instrument_id=instrument.id,
                        is_active=True,
                        created_at=FIXTURE_SOURCE_FETCHED_AT,
                        updated_at=FIXTURE_SOURCE_FETCHED_AT,
                        baseline_session=FIXTURE_ANALYSIS_DATE,
                        baseline_close_price=fixture.close_price,
                    )
                )
                memberships_created += 1
            elif not membership.is_active:
                membership.is_active = True
                membership.deactivated_at = None
                membership.reactivated_at = reactivation_time
                membership.updated_at = reactivation_time
                membership.baseline_session = FIXTURE_ANALYSIS_DATE
                membership.baseline_close_price = fixture.close_price

    await session.flush()

    return FixtureSeedSummary(
        companies_created=companies_created,
        instruments_created=instruments_created,
        snapshots_created=snapshots_created,
        trackings_created=trackings_created,
        memberships_created=memberships_created,
    )
