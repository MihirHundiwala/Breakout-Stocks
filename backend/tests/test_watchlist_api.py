from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    require_user_session,
)
from app.db.session import get_db_session
from app.main import app
from app.models import (
    AppUser,
    AnalysisJob,
    AnalysisJobType,
    AnalysisSnapshot,
    BenchmarkDailyCandle,
    Company,
    Instrument,
    MarketBenchmark,
    TrackedInstrument,
    TrackingOperationalState,
    UserRole,
    UserSession,
    FundamentalCoverageStatus,
    TechnicalStatus,
    UserWatchlistItem,
)
from app.services.watchlist import add_watchlist_memberships


TARGET_SESSION = date(2026, 7, 24)
CSRF_TOKEN = "synthetic-watchlist-csrf-token"
ADDED_AT = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)


async def persist_user(
    session: AsyncSession,
    username: str,
    role: UserRole = UserRole.USER,
) -> AppUser:
    user = AppUser(
        username=username,
        role=role,
        password_hash=("$argon2id$synthetic" if role == UserRole.USER else None),
    )
    session.add(user)
    await session.commit()
    return user


async def persist_instrument(
    session: AsyncSession,
    symbol: str,
) -> Instrument:
    instrument = Instrument(
        company=Company(name=f"{symbol} Industries Limited"),
        exchange="NSE",
        trading_symbol=symbol,
    )
    session.add(instrument)
    await session.commit()
    return instrument


def authenticated_session(user: AppUser) -> UserSession:
    created_at = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
    auth_user = AppUser(
        id=user.id,
        username=user.username,
        role=user.role,
        password_hash=user.password_hash,
        is_active=user.is_active,
    )
    return UserSession(
        user=auth_user,
        user_id=user.id,
        token_digest="a" * 64,
        csrf_token_digest=sha256(CSRF_TOKEN.encode("utf-8")).hexdigest(),
        created_at=created_at,
        expires_at=created_at + timedelta(hours=8),
    )


@asynccontextmanager
async def watchlist_client(
    db_session: AsyncSession,
    user: AppUser | None,
) -> AsyncIterator[AsyncClient]:
    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    if user is not None:
        app.dependency_overrides[require_user_session] = lambda: (
            authenticated_session(user)
        )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            if user is not None:
                client.cookies.set(CSRF_COOKIE_NAME, CSRF_TOKEN)
            yield client
    finally:
        app.dependency_overrides.clear()


def csrf_headers() -> dict[str, str]:
    return {CSRF_HEADER_NAME: CSRF_TOKEN}


@pytest.mark.anyio
async def test_watchlist_list_requires_authentication(
    db_session: AsyncSession,
) -> None:
    async with watchlist_client(db_session, None) as client:
        response = await client.get("/watchlist/instruments")

    assert response.status_code == 401
    assert response.json() == {"detail": "AUTHENTICATION_REQUIRED"}


@pytest.mark.anyio
async def test_watchlist_list_is_isolated_per_user(
    db_session: AsyncSession,
) -> None:
    first_user = await persist_user(db_session, "first-user")
    second_user = await persist_user(db_session, "second-user")
    first_instrument = await persist_instrument(db_session, "FIRST")
    second_instrument = await persist_instrument(db_session, "SECOND")
    await add_watchlist_memberships(
        db_session,
        user_id=first_user.id,
        instrument_ids=[first_instrument.id],
        target_session=TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT,
    )
    first_membership = await db_session.scalar(
        select(UserWatchlistItem).where(
            UserWatchlistItem.user_id == first_user.id,
            UserWatchlistItem.instrument_id == first_instrument.id,
        )
    )
    assert first_membership is not None
    first_membership.baseline_close_price = Decimal("100")
    db_session.add(
        AnalysisSnapshot(
            instrument_id=first_instrument.id,
            analysis_date=TARGET_SESSION,
            technical_status=TechnicalStatus.NO_SETUP,
            fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
            close_price=Decimal("112.50"),
            previous_close_price=Decimal("111"),
            source="UPSTOX",
            source_fetched_at=ADDED_AT,
            algorithm_version="test-v1",
            candle_revision="synthetic-v1",
            generated_at=ADDED_AT,
        )
    )
    await db_session.commit()
    await add_watchlist_memberships(
        db_session,
        user_id=second_user.id,
        instrument_ids=[second_instrument.id],
        target_session=TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT,
    )

    async with watchlist_client(db_session, first_user) as client:
        response = await client.get("/watchlist/instruments")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["watchlist_limit"] == 20
    assert response.json()["remaining_slots"] == 19
    assert response.json()["items"][0]["trading_symbol"] == "FIRST"
    assert response.json()["items"][0]["added_at"] == ADDED_AT.isoformat().replace(
        "+00:00", "Z"
    )
    assert response.json()["items"][0]["baseline_session"] == "2026-07-24"
    assert Decimal(response.json()["items"][0]["baseline_close_price"]) == Decimal("100")
    assert response.json()["items"][0]["latest_close_price"] == "112.5000"
    assert response.json()["items"][0]["movement_since_added_percent"] == "12.50"


@pytest.mark.anyio
async def test_admin_watchlist_has_no_limit(
    db_session: AsyncSession,
) -> None:
    admin = await persist_user(db_session, "admin", UserRole.ADMIN)

    async with watchlist_client(db_session, admin) as client:
        response = await client.get("/watchlist/instruments")

    assert response.status_code == 200
    assert response.json()["watchlist_limit"] is None
    assert response.json()["remaining_slots"] is None


@pytest.mark.anyio
async def test_remove_requires_csrf(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "csrf-user")

    async with watchlist_client(db_session, user) as client:
        response = await client.delete("/watchlist/instruments/1")

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF_VALIDATION_FAILED"}


@pytest.mark.anyio
async def test_admin_delete_purges_another_users_instrument(
    db_session: AsyncSession,
) -> None:
    admin = await persist_user(db_session, "global-delete-admin", UserRole.ADMIN)
    follower = await persist_user(db_session, "global-delete-follower")
    instrument = await persist_instrument(db_session, "GLOBALDELETE")
    instrument_id = instrument.id
    await add_watchlist_memberships(
        db_session,
        user_id=follower.id,
        instrument_ids=[instrument_id],
        target_session=TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT,
    )

    async with watchlist_client(db_session, admin) as client:
        response = await client.delete(
            f"/watchlist/instruments/{instrument_id}",
            headers=csrf_headers(),
        )

    assert response.status_code == 200
    assert response.json()["watchlist_limit"] is None
    assert await db_session.get(Instrument, instrument_id) is None
    assert await db_session.scalar(
        select(UserWatchlistItem).where(
            UserWatchlistItem.instrument_id == instrument_id
        )
    ) is None


@pytest.mark.anyio
async def test_manual_reanalysis_is_admin_only(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "ordinary-refresh-user")

    async with watchlist_client(db_session, user) as client:
        response = await client.post(
            "/admin/watchlist/instruments/refresh",
            headers=csrf_headers(),
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "ADMINISTRATOR_REQUIRED"}

    async with watchlist_client(db_session, user) as client:
        rerun_response = await client.post(
            "/admin/watchlist/instruments/rerun-algorithm",
            headers=csrf_headers(),
        )

    assert rerun_response.status_code == 403
    assert rerun_response.json() == {"detail": "ADMINISTRATOR_REQUIRED"}

    async with watchlist_client(db_session, user) as client:
        fundamental_response = await client.post(
            "/admin/watchlist/instruments/refresh-fundamentals",
            headers=csrf_headers(),
        )

    assert fundamental_response.status_code == 403
    assert fundamental_response.json() == {"detail": "ADMINISTRATOR_REQUIRED"}


@pytest.mark.anyio
async def test_algorithm_rerun_queues_stored_data_job_without_provider(
    db_session: AsyncSession,
) -> None:
    admin = await persist_user(db_session, "algorithm-admin", UserRole.ADMIN)
    instrument = await persist_instrument(db_session, "RERUN")
    db_session.add(
        TrackedInstrument(
            instrument_id=instrument.id,
            operational_state=TrackingOperationalState.READY,
            target_session=TARGET_SESSION,
            created_at=ADDED_AT,
            updated_at=ADDED_AT,
        )
    )
    benchmark = MarketBenchmark(
        code="NIFTY_500",
        name="Nifty 500",
        provider="UPSTOX",
        instrument_key="NSE_INDEX|Nifty 500",
        source_fetched_at=ADDED_AT,
    )
    db_session.add(benchmark)
    await db_session.flush()
    db_session.add(
        BenchmarkDailyCandle(
            benchmark_id=benchmark.id,
            trading_date=TARGET_SESSION,
            open_price=Decimal("100"),
            high_price=Decimal("101"),
            low_price=Decimal("99"),
            close_price=Decimal("100"),
            volume=1000,
            open_interest=0,
            source="UPSTOX",
            source_timestamp=ADDED_AT,
            fetched_at=ADDED_AT,
        )
    )
    await db_session.commit()

    async with watchlist_client(db_session, admin) as client:
        response = await client.post(
            "/admin/watchlist/instruments/rerun-algorithm",
            headers=csrf_headers(),
        )

    job = await db_session.scalar(select(AnalysisJob))
    assert response.status_code == 202
    assert response.json()["scheduled_count"] == 1
    assert response.json()["target_session"] == TARGET_SESSION.isoformat()
    assert job is not None
    assert job.job_type == AnalysisJobType.ANALYZE_INSTRUMENT
    assert job.reuse_stored_market_data is True


@pytest.mark.anyio
async def test_fundamental_refresh_queues_dedicated_jobs(
    db_session: AsyncSession,
) -> None:
    admin = await persist_user(db_session, "fundamental-admin", UserRole.ADMIN)
    instrument = await persist_instrument(db_session, "FUNDAMENTAL")
    db_session.add(
        TrackedInstrument(
            instrument_id=instrument.id,
            operational_state=TrackingOperationalState.READY,
            target_session=TARGET_SESSION,
            created_at=ADDED_AT,
            updated_at=ADDED_AT,
        )
    )
    benchmark = MarketBenchmark(
        code="NIFTY_500",
        name="Nifty 500",
        provider="UPSTOX",
        instrument_key="NSE_INDEX|Nifty 500",
        source_fetched_at=ADDED_AT,
    )
    db_session.add(benchmark)
    await db_session.flush()
    db_session.add(
        BenchmarkDailyCandle(
            benchmark_id=benchmark.id,
            trading_date=TARGET_SESSION,
            open_price=Decimal("100"),
            high_price=Decimal("101"),
            low_price=Decimal("99"),
            close_price=Decimal("100"),
            volume=1000,
            open_interest=0,
            source="UPSTOX",
            source_timestamp=ADDED_AT,
            fetched_at=ADDED_AT,
        )
    )
    await db_session.commit()

    async with watchlist_client(db_session, admin) as client:
        response = await client.post(
            "/admin/watchlist/instruments/refresh-fundamentals",
            headers=csrf_headers(),
        )

    job = await db_session.scalar(select(AnalysisJob))
    assert response.status_code == 202
    assert response.json()["scheduled_count"] == 1
    assert job is not None
    assert job.job_type == AnalysisJobType.REFRESH_FUNDAMENTALS
    assert job.reuse_stored_market_data is False


@pytest.mark.anyio
async def test_first_user_removal_keeps_shared_tracking_active(
    db_session: AsyncSession,
) -> None:
    first_user = await persist_user(db_session, "first-user")
    second_user = await persist_user(db_session, "second-user")
    instrument = await persist_instrument(db_session, "SHARED")
    for user in (first_user, second_user):
        await add_watchlist_memberships(
            db_session,
            user_id=user.id,
            instrument_ids=[instrument.id],
            target_session=TARGET_SESSION,
            normal_user_limit=20,
            occurred_at=ADDED_AT,
        )

    async with watchlist_client(db_session, first_user) as client:
        response = await client.delete(
            f"/watchlist/instruments/{instrument.id}",
            headers=csrf_headers(),
        )

    assert response.status_code == 200
    assert response.json()["removed"] is True
    tracking = await db_session.scalar(select(TrackedInstrument))
    assert tracking is not None
    assert tracking.is_active is True

    await db_session.commit()
    async with watchlist_client(db_session, second_user) as client:
        final_response = await client.delete(
            f"/watchlist/instruments/{instrument.id}",
            headers=csrf_headers(),
        )

    assert final_response.status_code == 200
    tracking = await db_session.scalar(select(TrackedInstrument))
    assert tracking is not None
    assert tracking.is_active is False
