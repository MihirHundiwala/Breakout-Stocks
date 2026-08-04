from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    FundamentalSnapshot,
    AppUser,
    AnalysisSnapshot,
    Company,
    Instrument,
    ProviderInstrumentIdentity,
    TrackedInstrument,
    UserWatchlistItem,
    DailyCandle,
)


@dataclass(frozen=True, slots=True)
class WatchlistRecord:
    membership: UserWatchlistItem
    tracked_instrument: TrackedInstrument
    instrument: Instrument
    company: Company
    latest_job: AnalysisJob | None
    latest_analysis: AnalysisSnapshot | None


async def list_watchlist_records(
    session: AsyncSession,
    user_id: int,
) -> list[WatchlistRecord]:
    latest_job_id = (
        select(AnalysisJob.id)
        .where(
            AnalysisJob.tracked_instrument_id
            == TrackedInstrument.id
        )
        .order_by(
            AnalysisJob.created_at.desc(),
            AnalysisJob.id.desc(),
        )
        .limit(1)
        .correlate(TrackedInstrument)
        .scalar_subquery()
    )
    latest_analysis_id = (
        select(AnalysisSnapshot.id)
        .where(AnalysisSnapshot.instrument_id == Instrument.id)
        .order_by(
            AnalysisSnapshot.analysis_date.desc(),
            AnalysisSnapshot.generated_at.desc(),
            AnalysisSnapshot.id.desc(),
        )
        .limit(1)
        .correlate(Instrument)
        .scalar_subquery()
    )
    statement = (
        select(
            UserWatchlistItem,
            TrackedInstrument,
            Instrument,
            Company,
            AnalysisJob,
            AnalysisSnapshot,
        )
        .join(
            Instrument,
            Instrument.id == UserWatchlistItem.instrument_id,
        )
        .join(
            TrackedInstrument,
            Instrument.id == TrackedInstrument.instrument_id,
        )
        .join(Company, Company.id == Instrument.company_id)
        .outerjoin(AnalysisJob, AnalysisJob.id == latest_job_id)
        .outerjoin(AnalysisSnapshot, AnalysisSnapshot.id == latest_analysis_id)
        .where(
            UserWatchlistItem.user_id == user_id,
            UserWatchlistItem.is_active.is_(True),
        )
        .order_by(
            Instrument.trading_symbol,
        )
    )
    rows = (await session.execute(statement)).all()
    return [
        WatchlistRecord(
            membership=row[0],
            tracked_instrument=row[1],
            instrument=row[2],
            company=row[3],
            latest_job=row[4],
            latest_analysis=row[5],
        )
        for row in rows
    ]


async def get_close_for_session(
    session: AsyncSession,
    *,
    instrument_id: int,
    trading_session: date,
) -> Decimal | None:
    candle_close = await session.scalar(
        select(DailyCandle.close_price).where(
            DailyCandle.instrument_id == instrument_id,
            DailyCandle.trading_date == trading_session,
        )
    )
    if candle_close is not None:
        return candle_close
    return await session.scalar(
        select(AnalysisSnapshot.close_price)
        .where(
            AnalysisSnapshot.instrument_id == instrument_id,
            AnalysisSnapshot.analysis_date == trading_session,
        )
        .order_by(
            AnalysisSnapshot.generated_at.desc(),
            AnalysisSnapshot.id.desc(),
        )
        .limit(1)
    )


async def get_user_for_update(
    session: AsyncSession,
    user_id: int,
) -> AppUser | None:
    return await session.scalar(
        select(AppUser).where(AppUser.id == user_id).with_for_update()
    )


async def get_membership_for_update(
    session: AsyncSession,
    *,
    user_id: int,
    instrument_id: int,
) -> UserWatchlistItem | None:
    return await session.scalar(
        select(UserWatchlistItem)
        .where(
            UserWatchlistItem.user_id == user_id,
            UserWatchlistItem.instrument_id == instrument_id,
        )
        .with_for_update()
    )


async def count_active_memberships_for_user(
    session: AsyncSession,
    user_id: int,
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(UserWatchlistItem)
        .where(
            UserWatchlistItem.user_id == user_id,
            UserWatchlistItem.is_active.is_(True),
        )
    )
    return int(count or 0)


async def count_active_followers_for_instrument(
    session: AsyncSession,
    instrument_id: int,
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(UserWatchlistItem)
        .where(
            UserWatchlistItem.instrument_id == instrument_id,
            UserWatchlistItem.is_active.is_(True),
        )
    )
    return int(count or 0)


async def get_instrument_for_update(
    session: AsyncSession,
    instrument_id: int,
) -> Instrument | None:
    statement = (
        select(Instrument)
        .where(Instrument.id == instrument_id)
        .with_for_update()
    )
    return await session.scalar(statement)


async def get_tracking_for_update(
    session: AsyncSession,
    instrument_id: int,
) -> TrackedInstrument | None:
    statement = (
        select(TrackedInstrument)
        .where(TrackedInstrument.instrument_id == instrument_id)
        .with_for_update()
    )
    return await session.scalar(statement)


async def get_latest_technical_job_for_update(
    session: AsyncSession,
    tracked_instrument_id: int,
) -> AnalysisJob | None:
    statement = (
        select(AnalysisJob)
        .where(
            AnalysisJob.tracked_instrument_id
            == tracked_instrument_id,
            AnalysisJob.job_type.in_(
                (
                    AnalysisJobType.ONBOARD_INSTRUMENT,
                    AnalysisJobType.ANALYZE_INSTRUMENT,
                )
            ),
        )
        .order_by(
            AnalysisJob.created_at.desc(),
            AnalysisJob.id.desc(),
        )
        .limit(1)
        .with_for_update()
    )
    return await session.scalar(statement)


async def get_active_fundamental_job_for_update(
    session: AsyncSession,
    tracked_instrument_id: int,
) -> AnalysisJob | None:
    statement = (
        select(AnalysisJob)
        .where(
            AnalysisJob.tracked_instrument_id == tracked_instrument_id,
            AnalysisJob.job_type == AnalysisJobType.REFRESH_FUNDAMENTALS,
            AnalysisJob.status.in_(
                (AnalysisJobStatus.PENDING, AnalysisJobStatus.RUNNING)
            ),
        )
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        .limit(1)
        .with_for_update()
    )
    return await session.scalar(statement)


async def has_fundamental_snapshot(
    session: AsyncSession,
    instrument_id: int,
) -> bool:
    snapshot_id = await session.scalar(
        select(FundamentalSnapshot.id)
        .where(FundamentalSnapshot.instrument_id == instrument_id)
        .limit(1)
    )
    return snapshot_id is not None


async def list_active_jobs_for_update(
    session: AsyncSession,
    tracked_instrument_id: int,
) -> list[AnalysisJob]:
    statement = (
        select(AnalysisJob)
        .where(
            AnalysisJob.tracked_instrument_id
            == tracked_instrument_id,
            AnalysisJob.status.in_(
                [
                    AnalysisJobStatus.PENDING,
                    AnalysisJobStatus.RUNNING,
                ]
            ),
        )
        .order_by(AnalysisJob.created_at, AnalysisJob.id)
        .with_for_update()
    )
    result = await session.scalars(statement)
    return list(result)


async def get_active_identity_with_instrument_for_update(
    session: AsyncSession,
    *,
    provider: str,
    instrument_key: str,
    isin: str,
) -> tuple[ProviderInstrumentIdentity, Instrument, Company] | None:
    statement = (
        select(ProviderInstrumentIdentity, Instrument, Company)
        .join(Instrument, Instrument.id == ProviderInstrumentIdentity.instrument_id)
        .join(Company, Company.id == Instrument.company_id)
        .where(
            ProviderInstrumentIdentity.provider == provider,
            ProviderInstrumentIdentity.effective_to.is_(None),
            (
                (ProviderInstrumentIdentity.instrument_key == instrument_key)
                | (ProviderInstrumentIdentity.isin == isin)
            ),
        )
        .with_for_update(of=(ProviderInstrumentIdentity, Instrument, Company))
    )
    row = (await session.execute(statement)).one_or_none()
    return (row[0], row[1], row[2]) if row is not None else None


async def get_instrument_by_symbol_for_update(
    session: AsyncSession,
    *,
    exchange: str,
    trading_symbol: str,
) -> tuple[Instrument, Company] | None:
    statement = (
        select(Instrument, Company)
        .join(Company, Company.id == Instrument.company_id)
        .where(
            Instrument.exchange == exchange,
            Instrument.trading_symbol == trading_symbol,
        )
        .with_for_update(of=(Instrument, Company))
    )
    row = (await session.execute(statement)).one_or_none()
    return (row[0], row[1]) if row is not None else None
