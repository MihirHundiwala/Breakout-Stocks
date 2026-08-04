from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_user_session
from app.db.session import get_db_session
from app.fixtures import seed_stock_fixtures
from app.main import app
from app.models import (
    AnalysisChartSnapshot,
    AnalysisSnapshot,
    AppUser,
    Company,
    FundamentalSnapshot,
    FundamentalCoverageStatus,
    Instrument,
    TechnicalStatus,
    TrackedInstrument,
    TrackingOperationalState,
    UserRole,
    UserSession,
    UserWatchlistItem,
)


async def persist_user_with_memberships(
    session: AsyncSession,
    username: str,
    symbols: list[str],
    role: UserRole = UserRole.USER,
) -> AppUser:
    user = AppUser(
        username=username,
        role=role,
        password_hash=(
            "$argon2id$synthetic" if role == UserRole.USER else None
        ),
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
    await session.commit()
    return user


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
        token_digest="c" * 64,
        csrf_token_digest="d" * 64,
        created_at=created_at,
        expires_at=created_at + timedelta(hours=8),
    )


async def request_stock_list(
    db_session: AsyncSession,
    user: AppUser | None,
    *,
    params: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
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
            response = await client.get("/stocks", params=params)
    finally:
        app.dependency_overrides.clear()

    return response.status_code, response.json()


@pytest.mark.anyio
async def test_stock_list_requires_login(db_session: AsyncSession) -> None:
    status_code, body = await request_stock_list(db_session, None)

    assert status_code == 401
    assert body == {"detail": "AUTHENTICATION_REQUIRED"}


@pytest.mark.anyio
async def test_stock_list_returns_an_empty_collection(
    db_session: AsyncSession,
) -> None:
    user = await persist_user_with_memberships(db_session, "empty-user", [])
    status_code, body = await request_stock_list(db_session, user)

    assert status_code == 200
    assert body == {
        "items": [],
        "count": 0,
        "page": 1,
        "page_size": 50,
        "total_pages": 0,
    }


@pytest.mark.anyio
async def test_stock_list_returns_only_users_fixture_results(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    user = await persist_user_with_memberships(
        db_session,
        "fixture-user",
        ["AURORA", "NEXUS", "HORIZON"],
    )

    status_code, body = await request_stock_list(db_session, user)

    assert status_code == 200
    assert body["count"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["total_pages"] == 1
    items = body["items"]
    assert isinstance(items, list)
    assert [item["trading_symbol"] for item in items] == [
        "AURORA",
        "NEXUS",
        "HORIZON",
    ]
    assert {
        key: items[0][key]
        for key in (
            "instrument_id",
            "company_name",
            "exchange",
            "trading_symbol",
            "analysis_date",
            "technical_status",
            "fundamental_coverage",
            "close_price",
            "day_change_percent",
            "market_cap_crore",
            "source",
            "source_fetched_at",
            "algorithm_version",
        )
    } == {
        "instrument_id": items[0]["instrument_id"],
        "company_name": "Aurora Engineering Limited",
        "exchange": "NSE",
        "trading_symbol": "AURORA",
        "analysis_date": "2026-07-22",
        "technical_status": "SETUP_FOUND",
        "fundamental_coverage": "COMPLETE",
        "close_price": "512.8000",
        "day_change_percent": "1.29",
        "market_cap_crore": None,
        "source": "FIXTURE",
        "source_fetched_at": "2026-07-22T12:00:00Z",
        "algorithm_version": "fixture-v1",
    }
    assert items[0]["setup_score"] is None
    assert items[0]["rejection_reasons"] == []
    assert items[0]["has_chart_data"] is False


@pytest.mark.anyio
async def test_setup_chart_is_lazy_and_respects_stock_authorization(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    instrument = await db_session.scalar(
        select(Instrument).where(Instrument.trading_symbol == "AURORA")
    )
    assert instrument is not None
    snapshot = await db_session.scalar(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.instrument_id == instrument.id
        )
    )
    assert snapshot is not None
    chart_candles = [
        {
            "date": (date(2026, 6, 23) + timedelta(days=index)).isoformat(),
            "open": "510",
            "high": "516",
            "low": "508",
            "close": "512",
            "volume": 1000,
        }
        for index in range(30)
    ]
    db_session.add_all([
        AnalysisChartSnapshot(
            analysis_snapshot_id=snapshot.id,
            timeframe="DAILY",
            period_count=29,
            window_start=date(2026, 6, 23),
            window_end=snapshot.analysis_date,
            resistance_price=Decimal("515"),
            resistance_zone_lower=Decimal("513.5"),
            resistance_zone_upper=Decimal("516.5"),
            resistance_touch_dates=["2026-07-01", "2026-07-15"],
            candles=chart_candles,
            schema_version="technical-chart-v2",
        ),
        AnalysisChartSnapshot(
            analysis_snapshot_id=snapshot.id,
            timeframe="WEEKLY",
            period_count=30,
            window_start=date(2026, 1, 1),
            window_end=snapshot.analysis_date,
            resistance_price=Decimal("520"),
            resistance_zone_lower=Decimal("517"),
            resistance_zone_upper=Decimal("523"),
            resistance_touch_dates=["2026-02-06", "2026-06-12"],
            candles=chart_candles,
            schema_version="technical-chart-v2",
        ),
    ])
    member = await persist_user_with_memberships(
        db_session,
        "chart-member",
        ["AURORA"],
    )
    outsider = await persist_user_with_memberships(
        db_session,
        "chart-outsider",
        [],
    )

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            app.dependency_overrides[require_user_session] = lambda: (
                authenticated_session(member)
            )
            allowed = await client.get(f"/stocks/{instrument.id}/chart")
            app.dependency_overrides[require_user_session] = lambda: (
                authenticated_session(outsider)
            )
            denied = await client.get(f"/stocks/{instrument.id}/chart")
    finally:
        app.dependency_overrides.clear()

    assert allowed.status_code == 200
    assert allowed.json()["company_name"] == "Aurora Engineering Limited"
    assert [item["timeframe"] for item in allowed.json()["charts"]] == [
        "DAILY",
        "WEEKLY",
    ]
    assert len(allowed.json()["charts"][0]["candles"]) == 30
    assert Decimal(
        allowed.json()["charts"][0]["resistance_zone_lower"]
    ) == Decimal("513.5")
    assert denied.status_code == 404


@pytest.mark.anyio
async def test_weekly_breakout_holding_is_visible_in_stock_list(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    instrument = await db_session.scalar(
        select(Instrument).where(Instrument.trading_symbol == "AURORA")
    )
    assert instrument is not None
    snapshot = await db_session.scalar(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.instrument_id == instrument.id
        )
    )
    assert snapshot is not None
    snapshot.technical_status = TechnicalStatus.BREAKOUT_HOLDING
    snapshot.consolidation_timeframe = "WEEKLY"
    snapshot.consolidation_window = 55
    snapshot.consolidation_start = date(2025, 7, 11)
    snapshot.resistance_price = Decimal("604.9750")
    chart_candles = [
        {
            "date": (
                snapshot.analysis_date - timedelta(weeks=54 - index)
            ).isoformat(),
            "open": "590",
            "high": "610",
            "low": "580",
            "close": "605",
            "volume": 1000,
        }
        for index in range(55)
    ]
    db_session.add(
        AnalysisChartSnapshot(
            analysis_snapshot_id=snapshot.id,
            timeframe="WEEKLY",
            period_count=55,
            window_start=snapshot.analysis_date - timedelta(weeks=54),
            window_end=snapshot.analysis_date,
            resistance_price=Decimal("604.9750"),
            resistance_zone_lower=Decimal("596.5050"),
            resistance_zone_upper=Decimal("613.4450"),
            resistance_touch_dates=["2025-08-22", "2026-07-17"],
            candles=chart_candles,
            schema_version="technical-chart-v3",
        )
    )
    user = await persist_user_with_memberships(
        db_session,
        "weekly-holder",
        ["AURORA"],
    )
    await db_session.commit()

    status_code, body = await request_stock_list(db_session, user)

    assert status_code == 200
    assert body["count"] == 1
    item = body["items"][0]
    assert item["technical_status"] == "BREAKOUT_HOLDING"
    assert item["consolidation_timeframe"] == "WEEKLY"
    assert item["consolidation_window"] == 55
    assert item["has_chart_data"] is True


@pytest.mark.anyio
async def test_stock_list_sorts_by_price_market_cap_and_watchlist_change(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    user = await persist_user_with_memberships(
        db_session,
        "sorted-user",
        ["AURORA", "NEXUS", "HORIZON"],
    )
    memberships = list(
        await db_session.scalars(
            select(UserWatchlistItem).where(
                UserWatchlistItem.user_id == user.id
            )
        )
    )
    for membership in memberships:
        membership.baseline_close_price = Decimal("100")
    instruments = list(await db_session.scalars(select(Instrument)))
    market_caps = {
        "AURORA": "2500",
        "NEXUS": "5000",
        "HORIZON": "1500",
    }
    db_session.add_all(
        [
            FundamentalSnapshot(
                instrument_id=instrument.id,
                as_of_date=date(2026, 7, 22),
                coverage=FundamentalCoverageStatus.COMPLETE,
                available_metric_count=1,
                expected_metric_count=1,
                metrics={
                    "profile": {
                        "sector_market_cap_inr_crore": market_caps[
                            instrument.trading_symbol
                        ]
                    }
                },
                source="FIXTURE",
                source_fetched_at=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
                schema_version="fixture-v1",
            )
            for instrument in instruments
        ]
    )
    await db_session.commit()

    day_status, day_body = await request_stock_list(
        db_session,
        user,
        params={"sort": "day_change_asc"},
    )
    cap_status, cap_body = await request_stock_list(
        db_session,
        user,
        params={"sort": "market_cap_desc"},
    )
    watchlist_status, watchlist_body = await request_stock_list(
        db_session,
        user,
        params={"sort": "watchlist_change_desc"},
    )
    invalid_status, _ = await request_stock_list(
        db_session,
        user,
        params={"sort": "not-a-sort"},
    )

    assert day_status == watchlist_status == 200
    assert [item["trading_symbol"] for item in day_body["items"]] == [
        "HORIZON",
        "NEXUS",
        "AURORA",
    ]
    assert cap_status == 200
    assert [item["trading_symbol"] for item in cap_body["items"]] == [
        "NEXUS",
        "AURORA",
        "HORIZON",
    ]
    assert cap_body["items"][0]["market_cap_crore"] == "5000"
    assert [
        item["trading_symbol"] for item in watchlist_body["items"]
    ] == ["NEXUS", "AURORA", "HORIZON"]
    assert invalid_status == 422


@pytest.mark.anyio
async def test_stock_detail_requires_an_active_membership(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    user = await persist_user_with_memberships(
        db_session,
        "detail-user",
        ["AURORA"],
    )
    instrument = await db_session.scalar(
        select(Instrument).where(Instrument.trading_symbol == "AURORA")
    )
    assert instrument is not None
    await db_session.commit()

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[require_user_session] = lambda: (
        authenticated_session(user)
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/stocks/{instrument.id}")
            hidden_response = await client.get("/stocks/999999")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["stock"]["trading_symbol"] == "AURORA"
    assert body["fundamentals"] is None
    assert body["periods"] == []
    assert hidden_response.status_code == 404
    assert hidden_response.json() == {"detail": "STOCK_ANALYSIS_NOT_FOUND"}


@pytest.mark.anyio
async def test_stock_detail_hides_another_users_membership(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    owner = await persist_user_with_memberships(
        db_session,
        "owner",
        ["AURORA"],
    )
    viewer = await persist_user_with_memberships(db_session, "viewer", [])
    instrument = await db_session.scalar(
        select(Instrument).where(Instrument.trading_symbol == "AURORA")
    )
    assert owner.id != viewer.id
    assert instrument is not None
    await db_session.commit()

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[require_user_session] = lambda: (
        authenticated_session(viewer)
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/stocks/{instrument.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "STOCK_ANALYSIS_NOT_FOUND"}


async def persist_analyzed_companies(
    session: AsyncSession,
    count: int,
) -> None:
    generated_at = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
    for number in range(1, count + 1):
        instrument = Instrument(
            company=Company(name=f"Pagination Company {number:03d} Limited"),
            exchange="NSE",
            trading_symbol=f"PAGE{number:03d}",
            is_preexisting_before_bulk_scan=False,
        )
        session.add_all(
            [
                TrackedInstrument(
                    instrument=instrument,
                    is_active=True,
                    operational_state=TrackingOperationalState.READY,
                    target_session=date(2026, 7, 24),
                    created_at=generated_at,
                    updated_at=generated_at,
                ),
                AnalysisSnapshot(
                    instrument=instrument,
                    analysis_date=date(2026, 7, 24),
                    technical_status=TechnicalStatus.NO_SETUP,
                    fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
                    close_price=Decimal("100"),
                    previous_close_price=Decimal("99"),
                    pivot_price=None,
                    breakout_confirmed_on=None,
                    source="FIXTURE",
                    source_fetched_at=generated_at,
                    algorithm_version="technical-v1",
                    candle_revision=f"pagination-{number}",
                    generated_at=generated_at,
                ),
            ]
        )
    await session.commit()


@pytest.mark.anyio
async def test_admin_list_paginates_fifty_rows_and_searches_all_pages(
    db_session: AsyncSession,
) -> None:
    await persist_analyzed_companies(db_session, 55)
    admin = await persist_user_with_memberships(
        db_session,
        "pagination-admin",
        [],
        role=UserRole.ADMIN,
    )

    first_status, first = await request_stock_list(db_session, admin)
    second_status, second = await request_stock_list(
        db_session,
        admin,
        params={"page": 2},
    )
    search_status, searched = await request_stock_list(
        db_session,
        admin,
        params={"search": "page055", "page": 1},
    )
    all_status, all_rows = await request_stock_list(
        db_session,
        admin,
        params={"page_size": "all"},
    )
    invalid_size_status, _ = await request_stock_list(
        db_session,
        admin,
        params={"page_size": "75"},
    )

    assert first_status == second_status == search_status == all_status == 200
    assert first["count"] == 55
    assert first["page_size"] == 50
    assert first["total_pages"] == 2
    assert len(first["items"]) == 50
    assert second["page"] == 2
    assert len(second["items"]) == 5
    assert searched["count"] == 1
    assert searched["total_pages"] == 1
    assert [item["trading_symbol"] for item in searched["items"]] == [
        "PAGE055"
    ]
    assert all_rows["page_size"] == 55
    assert all_rows["total_pages"] == 1
    assert len(all_rows["items"]) == 55
    assert invalid_size_status == 422


@pytest.mark.anyio
async def test_admin_list_exposes_terminal_analysis_failures_after_results(
    db_session: AsyncSession,
) -> None:
    await persist_analyzed_companies(db_session, 2)
    generated_at = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
    failed_instrument = Instrument(
        company=Company(name="New Listing Limited"),
        exchange="NSE",
        trading_symbol="NEWLIST",
        is_preexisting_before_bulk_scan=False,
    )
    db_session.add(
        TrackedInstrument(
            instrument=failed_instrument,
            is_active=True,
            operational_state=TrackingOperationalState.ANALYSIS_FAILED,
            target_session=date(2026, 7, 29),
            terminal_data_error_session=date(2026, 7, 29),
            terminal_data_error_code="INSUFFICIENT_LISTING_HISTORY",
            created_at=generated_at,
            updated_at=generated_at,
        )
    )
    await db_session.commit()
    admin = await persist_user_with_memberships(
        db_session,
        "failure-admin",
        [],
        role=UserRole.ADMIN,
    )

    status_code, body = await request_stock_list(
        db_session,
        admin,
        params={"sort": "status", "page_size": "all"},
    )

    assert status_code == 200
    assert body["count"] == 3
    assert [item["trading_symbol"] for item in body["items"]] == [
        "PAGE001",
        "PAGE002",
        "NEWLIST",
    ]
    failed = body["items"][-1]
    assert failed["analysis_date"] is None
    assert failed["technical_status"] is None
    assert failed["close_price"] is None
    assert failed["day_change_percent"] is None
    assert failed["source"] is None
    assert failed["source_fetched_at"] is None
    assert failed["algorithm_version"] is None
    assert failed["has_chart_data"] is False
    assert failed["fundamental_coverage"] == "UNKNOWN"
    assert failed["operational_state"] == "ANALYSIS_FAILED"
    assert failed["analysis_error_session"] == "2026-07-29"
    assert (
        failed["analysis_error_code"]
        == "INSUFFICIENT_LISTING_HISTORY"
    )


@pytest.mark.anyio
async def test_bulk_instrument_is_admin_only_even_with_user_membership(
    db_session: AsyncSession,
) -> None:
    await seed_stock_fixtures(db_session)
    instrument = await db_session.scalar(
        select(Instrument).where(Instrument.trading_symbol == "AURORA")
    )
    assert instrument is not None
    instrument.is_preexisting_before_bulk_scan = False
    db_session.add(
        TrackedInstrument(
            instrument_id=instrument.id,
            is_active=True,
            operational_state=TrackingOperationalState.READY,
            target_session=date(2026, 7, 22),
            created_at=datetime(2026, 7, 22, 16, 0, tzinfo=UTC),
            updated_at=datetime(2026, 7, 22, 16, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()
    user = await persist_user_with_memberships(
        db_session,
        "bulk-hidden-user",
        ["AURORA"],
    )
    admin = await persist_user_with_memberships(
        db_session,
        "bulk-visible-admin",
        [],
        role=UserRole.ADMIN,
    )

    user_status, user_list = await request_stock_list(db_session, user)
    admin_status, admin_list = await request_stock_list(db_session, admin)

    assert user_status == admin_status == 200
    assert user_list["count"] == 0
    assert "AURORA" not in [item["trading_symbol"] for item in user_list["items"]]
    assert "AURORA" in [item["trading_symbol"] for item in admin_list["items"]]

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            app.dependency_overrides[require_user_session] = lambda: (
                authenticated_session(user)
            )
            user_detail = await client.get(f"/stocks/{instrument.id}")
            app.dependency_overrides[require_user_session] = lambda: (
                authenticated_session(admin)
            )
            admin_detail = await client.get(f"/stocks/{instrument.id}")
    finally:
        app.dependency_overrides.clear()

    assert user_detail.status_code == 404
    assert admin_detail.status_code == 200
