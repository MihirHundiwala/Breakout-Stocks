from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.models import UserRole, UserSession
from app.services.auth import (
    AuthConfig,
    AuthenticationRequiredError,
    CsrfValidationError,
    authenticate_user_session,
    record_authenticated_activity,
    validate_csrf_token,
)


SESSION_COOKIE_NAME = "breakout_admin_session"
CSRF_COOKIE_NAME = "breakout_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


async def get_auth_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


def get_auth_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthConfig:
    return AuthConfig(
        admin_username=settings.admin_username,
        admin_password_hash_b64=settings.admin_password_hash_b64,
        session_ttl_seconds=settings.admin_session_ttl_seconds,
        cookie_secure=settings.admin_cookie_secure,
        normal_user_watchlist_limit=settings.normal_user_watchlist_limit,
    )


async def require_user_session(
    session: Annotated[AsyncSession, Depends(get_auth_db_session)],
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> UserSession:
    try:
        user_session = await authenticate_user_session(session, session_token)
        await record_authenticated_activity(
            session,
            user_session,
            occurred_at=datetime.now(UTC),
        )
        return user_session
    except AuthenticationRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AUTHENTICATION_REQUIRED",
        ) from error


def require_admin_session(
    user_session: Annotated[UserSession, Depends(require_user_session)],
) -> UserSession:
    if user_session.user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ADMINISTRATOR_REQUIRED",
        )
    return user_session


def _validate_csrf(
    user_session: UserSession,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> UserSession:
    try:
        validate_csrf_token(user_session, csrf_cookie, csrf_header)
    except CsrfValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF_VALIDATION_FAILED",
        ) from error
    return user_session


def require_user_csrf(
    user_session: Annotated[UserSession, Depends(require_user_session)],
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
) -> UserSession:
    return _validate_csrf(user_session, csrf_cookie, csrf_header)


def require_csrf(
    user_session: Annotated[UserSession, Depends(require_admin_session)],
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
) -> UserSession:
    return _validate_csrf(user_session, csrf_cookie, csrf_header)


# Compatibility name used by current tests while callers migrate.
get_admin_auth_config = get_auth_config
