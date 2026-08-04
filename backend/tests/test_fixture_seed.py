import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.fixtures import seed_stock_fixtures
from app.models import (
    AnalysisSnapshot,
    AppUser,
    Company,
    Instrument,
    TrackedInstrument,
    UserRole,
    UserWatchlistItem,
)


@pytest.mark.anyio
async def test_fixture_seed_is_idempotent(
    db_session: AsyncSession,
) -> None:
    admin = AppUser(
        username="admin",
        role=UserRole.ADMIN,
        password_hash=None,
    )
    db_session.add(admin)
    await db_session.flush()
    first_summary = await seed_stock_fixtures(
        db_session,
        owner_user_id=admin.id,
    )
    second_summary = await seed_stock_fixtures(
        db_session,
        owner_user_id=admin.id,
    )

    company_count = await db_session.scalar(
        select(func.count()).select_from(Company)
    )
    instrument_count = await db_session.scalar(
        select(func.count()).select_from(Instrument)
    )
    snapshot_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisSnapshot)
    )
    tracking_count = await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    )
    membership_count = await db_session.scalar(
        select(func.count()).select_from(UserWatchlistItem)
    )

    assert first_summary.companies_created == 3
    assert first_summary.instruments_created == 3
    assert first_summary.snapshots_created == 3
    assert first_summary.trackings_created == 3
    assert first_summary.memberships_created == 3
    assert second_summary.companies_created == 0
    assert second_summary.instruments_created == 0
    assert second_summary.snapshots_created == 0
    assert second_summary.trackings_created == 0
    assert second_summary.memberships_created == 0
    assert company_count == 3
    assert instrument_count == 3
    assert snapshot_count == 3
    assert tracking_count == 3
    assert membership_count == 3
