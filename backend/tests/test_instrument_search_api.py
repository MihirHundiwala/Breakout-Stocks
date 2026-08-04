from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    require_user_session,
)
from app.api.dependencies.providers import get_upstox_provider
from app.core.config import get_settings
from app.db.session import get_db_session
from app.main import app
from app.models import (
    AnalysisJob,
    AnalysisJobType,
    AppUser,
    Instrument,
    ProviderInstrumentIdentity,
    TrackedInstrument,
    UserRole,
    UserSession,
    UserWatchlistItem,
)
from app.providers.contracts import DailyCandle, ExchangeSession, InstrumentCandidate


CSRF_TOKEN = "synthetic-search-csrf"
CANDIDATE = InstrumentCandidate(
    company_name="Reliance Industries Limited",
    exchange="NSE",
    trading_symbol="RELIANCE",
    isin="INE002A01018",
    instrument_key="NSE_EQ|INE002A01018",
)
SECOND_CANDIDATE = InstrumentCandidate(
    company_name="Example Industries Limited",
    exchange="NSE",
    trading_symbol="EXAMPLE",
    isin="INE123A01016",
    instrument_key="NSE_EQ|INE123A01016",
)


class FakeUpstoxProvider:
    def __init__(
        self,
        *,
        candidates: tuple[InstrumentCandidate, ...] = (
            CANDIDATE,
            SECOND_CANDIDATE,
        ),
    ) -> None:
        self.candidates = candidates
        self.queries: list[str] = []

    async def search_nse_equities(
        self,
        *,
        query: str,
        limit: int = 20,
    ) -> tuple[InstrumentCandidate, ...]:
        self.queries.append(query)
        normalized = query.upper()
        return tuple(
            item
            for item in self.candidates
            if normalized in {item.isin, item.trading_symbol}
            or query.lower() in item.company_name.lower()
        )[:limit]

    async def get_nse_session(self, session_date: date) -> ExchangeSession:
        return ExchangeSession(
            session_date=session_date,
            is_open=session_date.weekday() < 5,
        )

    async def get_daily_candles(self, **kwargs: object) -> tuple[DailyCandle, ...]:
        session_date = kwargs["to_date"]
        assert isinstance(session_date, date)
        return (
            DailyCandle(
                trading_date=session_date,
                timestamp=datetime.combine(
                    session_date,
                    datetime.min.time(),
                    tzinfo=UTC,
                ),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=1000,
                open_interest=0,
            ),
        )


async def persist_user(session: AsyncSession, username: str) -> AppUser:
    user = AppUser(
        username=username,
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    session.add(user)
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
        token_digest="b" * 64,
        csrf_token_digest=sha256(CSRF_TOKEN.encode()).hexdigest(),
        created_at=created_at,
        expires_at=created_at + timedelta(hours=8),
    )


@asynccontextmanager
async def client_for(
    db_session: AsyncSession,
    provider: FakeUpstoxProvider,
    user: AppUser | None,
    *,
    normal_user_limit: int = 20,
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    settings = get_settings().model_copy(
        update={"normal_user_watchlist_limit": normal_user_limit}
    )
    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_upstox_provider] = lambda: provider
    app.dependency_overrides[get_settings] = lambda: settings
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
async def test_search_requires_login(db_session: AsyncSession) -> None:
    provider = FakeUpstoxProvider()
    async with client_for(db_session, provider, None) as client:
        response = await client.get(
            "/watchlist/instruments/search",
            params={"query": "RELIANCE"},
        )

    assert response.status_code == 401
    assert provider.queries == []


@pytest.mark.anyio
async def test_search_returns_validated_public_candidates(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "search-user")
    provider = FakeUpstoxProvider()
    async with client_for(db_session, provider, user) as client:
        response = await client.get(
            "/watchlist/instruments/search",
            params={"query": "RELIANCE"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "company_name": "Reliance Industries Limited",
                "exchange": "NSE",
                "trading_symbol": "RELIANCE",
                "isin": "INE002A01018",
            }
        ],
        "count": 1,
    }


@pytest.mark.anyio
async def test_batch_add_requires_csrf(db_session: AsyncSession) -> None:
    user = await persist_user(db_session, "csrf-user")
    async with client_for(
        db_session,
        FakeUpstoxProvider(),
        user,
    ) as client:
        response = await client.post(
            "/watchlist/instruments",
            json={"isins": [CANDIDATE.isin]},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_batch_add_revalidates_identity_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "batch-user")
    provider = FakeUpstoxProvider()
    async with client_for(db_session, provider, user) as client:
        first = await client.post(
            "/watchlist/instruments",
            json={"isins": [CANDIDATE.isin]},
            headers=csrf_headers(),
        )
        repeated = await client.post(
            "/watchlist/instruments",
            json={"isins": [CANDIDATE.isin]},
            headers=csrf_headers(),
        )

    assert first.status_code == 200
    assert first.json()["items"][0]["membership_created"] is True
    assert first.json()["items"][0]["shared_analysis_started"] is True
    assert repeated.status_code == 200
    assert repeated.json()["items"][0]["already_in_watchlist"] is True
    assert repeated.json()["items"][0]["shared_analysis_started"] is False
    assert await db_session.scalar(
        select(func.count()).select_from(UserWatchlistItem)
    ) == 1
    assert await db_session.scalar(
        select(func.count()).select_from(Instrument)
    ) == 1
    assert await db_session.scalar(
        select(func.count()).select_from(ProviderInstrumentIdentity)
    ) == 1
    assert await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    ) == 1
    assert await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    ) == 2
    assert set(await db_session.scalars(select(AnalysisJob.job_type))) == {
        AnalysisJobType.ONBOARD_INSTRUMENT,
        AnalysisJobType.REFRESH_FUNDAMENTALS,
    }


@pytest.mark.anyio
async def test_second_user_does_not_start_duplicate_analysis(
    db_session: AsyncSession,
) -> None:
    first_user = await persist_user(db_session, "first-user")
    second_user = await persist_user(db_session, "second-user")
    provider = FakeUpstoxProvider()

    for user in (first_user, second_user):
        async with client_for(db_session, provider, user) as client:
            response = await client.post(
                "/watchlist/instruments",
                json={"isins": [CANDIDATE.isin]},
                headers=csrf_headers(),
            )
        assert response.status_code == 200

    assert await db_session.scalar(
        select(func.count()).select_from(UserWatchlistItem)
    ) == 2
    assert await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    ) == 1
    assert await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    ) == 2


@pytest.mark.anyio
async def test_over_limit_batch_creates_no_memberships_or_analysis(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "limited-user")
    provider = FakeUpstoxProvider()
    async with client_for(
        db_session,
        provider,
        user,
        normal_user_limit=1,
    ) as client:
        response = await client.post(
            "/watchlist/instruments",
            json={"isins": [CANDIDATE.isin, SECOND_CANDIDATE.isin]},
            headers=csrf_headers(),
        )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "WATCHLIST_LIMIT_EXCEEDED",
        "limit": 1,
        "active_count": 0,
        "requested_count": 2,
    }
    assert await db_session.scalar(
        select(func.count()).select_from(UserWatchlistItem)
    ) == 0
    assert await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    ) == 0
    assert await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    ) == 0


@pytest.mark.anyio
async def test_batch_add_rejects_unknown_isin(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "unknown-user")
    async with client_for(
        db_session,
        FakeUpstoxProvider(candidates=()),
        user,
    ) as client:
        response = await client.post(
            "/watchlist/instruments",
            json={"isins": [CANDIDATE.isin]},
            headers=csrf_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "UPSTOX_INSTRUMENT_NOT_FOUND"}
