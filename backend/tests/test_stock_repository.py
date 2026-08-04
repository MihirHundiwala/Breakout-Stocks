from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.fixtures import seed_stock_fixtures
from app.models import (
    AnalysisSnapshot,
    AppUser,
    FundamentalCoverageStatus,
    Instrument,
    TechnicalStatus,
    UserRole,
    UserWatchlistItem,
)
from app.repositories.stocks import list_latest_stock_analyses


async def persist_user_with_memberships(
    session: AsyncSession,
    symbols: list[str],
) -> AppUser:
    user = AppUser(
        username="stock-reader",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    session.add(user)
    await session.flush()
    instruments = list(
        await session.scalars(
            select(Instrument).where(Instrument.trading_symbol.in_(symbols))
        )
    )
    session.add_all(
        [
            UserWatchlistItem(
                user_id=user.id,
                instrument_id=item.id,
                baseline_session=date(2026, 7, 22),
            )
            for item in instruments
        ]
    )
    await session.flush()
    return user


@pytest.mark.anyio
async def test_repository_returns_only_latest_valid_snapshot(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    user = await persist_user_with_memberships(
        db_session,
        ["AURORA", "NEXUS", "HORIZON"],
    )
    instrument = await db_session.scalar(
        select(Instrument).where(
            Instrument.trading_symbol == "NEXUS"
        )
    )
    assert instrument is not None

    db_session.add(
        AnalysisSnapshot(
            instrument=instrument,
            analysis_date=date(2026, 7, 23),
            technical_status=TechnicalStatus.NO_SETUP,
            fundamental_coverage=(
                FundamentalCoverageStatus.PARTIAL
            ),
            close_price=Decimal("841.0000"),
            previous_close_price=Decimal("847.3000"),
            pivot_price=None,
            breakout_confirmed_on=None,
            source="FIXTURE",
            source_fetched_at=datetime(
                2026,
                7,
                23,
                12,
                0,
                tzinfo=UTC,
            ),
            algorithm_version="fixture-v1",
            candle_revision="synthetic-v2",
        )
    )
    await db_session.flush()

    result = await list_latest_stock_analyses(
        db_session,
        user_id=user.id,
        is_admin=False,
        page=1,
        page_size=50,
        search=None,
        sort="status",
    )
    records_by_symbol = {
        instrument.trading_symbol: snapshot
        for _, instrument, snapshot, *_ in result.records
    }

    assert result.count == 3
    assert len(result.records) == 3
    assert records_by_symbol["NEXUS"].analysis_date == date(
        2026,
        7,
        23,
    )
    assert (
        records_by_symbol["NEXUS"].technical_status
        == TechnicalStatus.NO_SETUP
    )


@pytest.mark.anyio
async def test_repository_returns_only_the_users_active_memberships(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    user = await persist_user_with_memberships(db_session, ["AURORA"])
    other_user = AppUser(
        username="other-reader",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    db_session.add(other_user)
    await db_session.flush()
    horizon = await db_session.scalar(
        select(Instrument).where(Instrument.trading_symbol == "HORIZON")
    )
    assert horizon is not None
    db_session.add(
        UserWatchlistItem(
            user_id=other_user.id,
            instrument_id=horizon.id,
            baseline_session=date(2026, 7, 22),
        )
    )
    await db_session.flush()

    result = await list_latest_stock_analyses(
        db_session,
        user_id=user.id,
        is_admin=False,
        page=1,
        page_size=50,
        search=None,
        sort="status",
    )

    assert result.count == 1
    assert [record[1].trading_symbol for record in result.records] == ["AURORA"]
