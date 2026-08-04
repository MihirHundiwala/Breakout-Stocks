from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from httpx2 import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.dependencies.auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    get_admin_auth_config,
    get_auth_db_session,
)
from app.main import app
from app.models import AppUser, UserRole, UserSession
from app.services.auth import (
    AuthConfig,
    AuthenticationRequiredError,
    authenticate_user_session,
    hash_normal_user_password,
    hash_admin_password_to_base64,
    login_user,
    record_authenticated_activity,
)


ADMIN_PASSWORD = "synthetic-test-password"
ADMIN_PASSWORD_HASH_B64 = hash_admin_password_to_base64(ADMIN_PASSWORD)
AUTH_CONFIG = AuthConfig(
    admin_username="admin",
    admin_password_hash_b64=SecretStr(ADMIN_PASSWORD_HASH_B64),
    session_ttl_seconds=3600,
    cookie_secure=False,
    normal_user_watchlist_limit=20,
)


async def build_auth_client(
    db_session: AsyncSession,
    config: AuthConfig = AUTH_CONFIG,
) -> AsyncIterator[AsyncClient]:
    async def override_auth_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    def override_auth_config() -> AuthConfig:
        return config

    app.dependency_overrides[get_auth_db_session] = (
        override_auth_db_session
    )
    app.dependency_overrides[get_admin_auth_config] = (
        override_auth_config
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_login_sets_cookies_and_persists_only_digests(
    db_session: AsyncSession,
) -> None:
    async for client in build_auth_client(db_session):
        response = await client.post(
            "/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )

        assert response.status_code == 200
        assert response.json()["authenticated"] is True
        assert response.json()["username"] == "admin"
        assert response.json()["role"] == "ADMIN"
        assert response.json()["watchlist_limit"] is None
        assert set(response.json()) == {
            "authenticated",
            "username",
            "role",
            "watchlist_limit",
            "expires_at",
        }

        session_token = client.cookies.get(SESSION_COOKIE_NAME)
        csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
        assert session_token is not None
        assert csrf_token is not None

        set_cookie_headers = response.headers.get_list("set-cookie")
        session_cookie_header = next(
            value
            for value in set_cookie_headers
            if value.startswith(f"{SESSION_COOKIE_NAME}=")
        )
        csrf_cookie_header = next(
            value
            for value in set_cookie_headers
            if value.startswith(f"{CSRF_COOKIE_NAME}=")
        )
        assert "HttpOnly" in session_cookie_header
        assert "SameSite=lax" in session_cookie_header
        assert "HttpOnly" not in csrf_cookie_header

        stored_session = await db_session.scalar(
            select(UserSession).options(joinedload(UserSession.user))
        )
        assert stored_session is not None
        assert stored_session.user.role == UserRole.ADMIN
        assert stored_session.token_digest == sha256(
            session_token.encode("utf-8")
        ).hexdigest()
        assert stored_session.csrf_token_digest == sha256(
            csrf_token.encode("utf-8")
        ).hexdigest()
        assert session_token != stored_session.token_digest
        assert csrf_token != stored_session.csrf_token_digest

        session_response = await client.get("/auth/session")
        assert session_response.status_code == 200
        assert session_response.json()["username"] == "admin"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("unknown", ADMIN_PASSWORD),
        ("admin", "wrong-password"),
    ],
)
async def test_login_rejects_credentials_with_one_generic_error(
    db_session: AsyncSession,
    username: str,
    password: str,
) -> None:
    async for client in build_auth_client(db_session):
        response = await client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "INVALID_CREDENTIALS"}
    assert await db_session.scalar(
        select(func.count()).select_from(UserSession)
    ) == 0


@pytest.mark.anyio
async def test_login_reports_missing_server_configuration(
    db_session: AsyncSession,
) -> None:
    config = AuthConfig(
        admin_username="admin",
        admin_password_hash_b64=None,
        session_ttl_seconds=3600,
        cookie_secure=False,
        normal_user_watchlist_limit=20,
    )
    async for client in build_auth_client(db_session, config):
        response = await client.post(
            "/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "AUTH_NOT_CONFIGURED"}


@pytest.mark.anyio
async def test_login_reports_invalid_server_configuration(
    db_session: AsyncSession,
) -> None:
    config = AuthConfig(
        admin_username="admin",
        admin_password_hash_b64=SecretStr(
            "JGFyZ29uMi1ub3QtdmFsaWQ="
        ),
        session_ttl_seconds=3600,
        cookie_secure=False,
        normal_user_watchlist_limit=20,
    )
    async for client in build_auth_client(db_session, config):
        response = await client.post(
            "/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "AUTH_NOT_CONFIGURED"}


@pytest.mark.anyio
async def test_session_requires_an_active_cookie(
    db_session: AsyncSession,
) -> None:
    async for client in build_auth_client(db_session):
        response = await client.get("/auth/session")

    assert response.status_code == 401
    assert response.json() == {"detail": "AUTHENTICATION_REQUIRED"}


@pytest.mark.anyio
async def test_logout_requires_csrf_and_revokes_the_session(
    db_session: AsyncSession,
) -> None:
    async for client in build_auth_client(db_session):
        login_response = await client.post(
            "/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert login_response.status_code == 200
        csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
        assert csrf_token is not None

        missing_csrf_response = await client.post("/auth/logout")
        assert missing_csrf_response.status_code == 403
        assert missing_csrf_response.json() == {
            "detail": "CSRF_VALIDATION_FAILED"
        }

        mismatched_csrf_response = await client.post(
            "/auth/logout",
            headers={CSRF_HEADER_NAME: "wrong-csrf-token"},
        )
        assert mismatched_csrf_response.status_code == 403
        assert mismatched_csrf_response.json() == {
            "detail": "CSRF_VALIDATION_FAILED"
        }

        logout_response = await client.post(
            "/auth/logout",
            headers={CSRF_HEADER_NAME: csrf_token},
        )
        assert logout_response.status_code == 204
        assert logout_response.content == b""

        session_response = await client.get("/auth/session")
        assert session_response.status_code == 401

    stored_session = await db_session.scalar(select(UserSession))
    assert stored_session is not None
    assert stored_session.revoked_at is not None


@pytest.mark.anyio
async def test_expired_session_is_rejected(
    db_session: AsyncSession,
) -> None:
    created_at = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
    result = await login_user(
        db_session,
        AUTH_CONFIG,
        "admin",
        ADMIN_PASSWORD,
        occurred_at=created_at,
    )

    with pytest.raises(AuthenticationRequiredError):
        await authenticate_user_session(
            db_session,
            result.session_token,
            occurred_at=created_at + timedelta(hours=1, seconds=1),
        )


@pytest.mark.anyio
async def test_auth_service_rejects_naive_event_time(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        await login_user(
            db_session,
            AUTH_CONFIG,
            "admin",
            ADMIN_PASSWORD,
            occurred_at=datetime(2026, 7, 25, 10, 0),
        )


@pytest.mark.anyio
async def test_authenticated_activity_is_written_at_most_every_15_minutes(
    db_session: AsyncSession,
) -> None:
    logged_in_at = datetime(2026, 8, 1, 6, 0, tzinfo=UTC)
    result = await login_user(
        db_session,
        AUTH_CONFIG,
        "admin",
        ADMIN_PASSWORD,
        occurred_at=logged_in_at,
    )
    user_session = await authenticate_user_session(
        db_session,
        result.session_token,
        occurred_at=logged_in_at,
    )

    await record_authenticated_activity(
        db_session,
        user_session,
        occurred_at=logged_in_at + timedelta(minutes=5),
    )
    assert user_session.user.last_active_at == logged_in_at

    await record_authenticated_activity(
        db_session,
        user_session,
        occurred_at=logged_in_at + timedelta(minutes=16),
    )
    assert user_session.user.last_active_at == logged_in_at + timedelta(
        minutes=16
    )


@pytest.mark.anyio
async def test_normal_user_login_returns_role_and_configured_limit(
    db_session: AsyncSession,
) -> None:
    password = "normal-user-test-password"
    db_session.add(
        AppUser(
            username="mihir",
            role=UserRole.USER,
            password_hash=hash_normal_user_password(password),
        )
    )
    await db_session.commit()

    async for client in build_auth_client(db_session):
        response = await client.post(
            "/auth/login",
            json={"username": " MIHIR ", "password": password},
        )

    assert response.status_code == 200
    assert response.json()["username"] == "mihir"
    assert response.json()["role"] == "USER"
    assert response.json()["watchlist_limit"] == 20


@pytest.mark.anyio
async def test_signup_creates_only_a_normal_user_and_signs_them_in(
    db_session: AsyncSession,
) -> None:
    async for client in build_auth_client(db_session):
        response = await client.post(
            "/auth/signup",
            json={
                "username": "  New.Investor  ",
                "password": "a-secure-test-password",
            },
        )

    assert response.status_code == 201
    assert response.json()["username"] == "new.investor"
    assert response.json()["role"] == "USER"
    assert response.json()["watchlist_limit"] == 20

    user = await db_session.scalar(
        select(AppUser).where(AppUser.username == "new.investor")
    )
    assert user is not None
    assert user.role == UserRole.USER
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2")
    assert user.password_hash != "a-secure-test-password"


@pytest.mark.anyio
@pytest.mark.parametrize("username", ["admin", "invalid name", "ab"])
async def test_signup_rejects_reserved_or_invalid_usernames(
    db_session: AsyncSession,
    username: str,
) -> None:
    async for client in build_auth_client(db_session):
        response = await client.post(
            "/auth/signup",
            json={"username": username, "password": "a-secure-test-password"},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "USERNAME_UNAVAILABLE"}


@pytest.mark.anyio
async def test_signup_rejects_duplicate_username_and_short_password(
    db_session: AsyncSession,
) -> None:
    async for client in build_auth_client(db_session):
        first = await client.post(
            "/auth/signup",
            json={"username": "investor", "password": "a-secure-test-password"},
        )
        assert first.status_code == 201

        duplicate = await client.post(
            "/auth/signup",
            json={"username": "INVESTOR", "password": "another-test-password"},
        )
        short = await client.post(
            "/auth/signup",
            json={"username": "another-user", "password": "too-short"},
        )

    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "USERNAME_UNAVAILABLE"}
    assert short.status_code == 422
    assert short.json() == {"detail": "PASSWORD_TOO_SHORT"}
