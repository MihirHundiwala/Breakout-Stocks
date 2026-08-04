from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    get_auth_db_session,
    require_user_session,
)
from app.core.config import get_settings
from app.db.session import get_db_session
from app.main import app
from app.models import AppUser, UserRole, UserSession


CSRF_TOKEN = "synthetic-telegram-csrf"


def authenticated_session(user: AppUser) -> UserSession:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    return UserSession(
        user=AppUser(
            id=user.id,
            username=user.username,
            role=user.role,
            password_hash=user.password_hash,
        ),
        user_id=user.id,
        token_digest="a" * 64,
        csrf_token_digest=sha256(CSRF_TOKEN.encode()).hexdigest(),
        created_at=now,
        expires_at=now + timedelta(hours=8),
    )


@asynccontextmanager
async def telegram_client(
    db_session: AsyncSession,
    user: AppUser,
    *,
    enabled: bool,
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    settings = get_settings().model_copy(update={
        "telegram_notifications_enabled": enabled,
        "telegram_bot_username": "breakout_tracker_bot" if enabled else None,
    })
    app.dependency_overrides[get_auth_db_session] = override_db
    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[require_user_session] = lambda: authenticated_session(user)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            client.cookies.set(CSRF_COOKIE_NAME, CSRF_TOKEN)
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_connect_endpoint_returns_direct_one_time_bot_link(
    db_session: AsyncSession,
) -> None:
    user = AppUser(
        username="telegram-api-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    db_session.add(user)
    await db_session.commit()

    async with telegram_client(db_session, user, enabled=True) as client:
        response = await client.post(
            "/telegram/connection",
            headers={CSRF_HEADER_NAME: CSRF_TOKEN},
        )
        status_response = await client.get("/telegram/connection")

    assert response.status_code == 200
    assert response.json()["bot_url"].startswith(
        "https://t.me/breakout_tracker_bot?start="
    )
    assert response.json()["pending"] is True
    assert "username" not in response.json()["bot_url"]
    assert status_response.json() == {
        "available": True,
        "connected": False,
        "pending": True,
        "username": None,
    }


@pytest.mark.anyio
async def test_connect_endpoint_reports_disabled_configuration(
    db_session: AsyncSession,
) -> None:
    user = AppUser(
        username="telegram-disabled-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    db_session.add(user)
    await db_session.commit()

    async with telegram_client(db_session, user, enabled=False) as client:
        response = await client.post(
            "/telegram/connection",
            headers={CSRF_HEADER_NAME: CSRF_TOKEN},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "TELEGRAM_NOT_CONFIGURED"}
