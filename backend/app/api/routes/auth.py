from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    get_auth_config,
    get_auth_db_session,
    require_user_csrf,
    require_user_session,
)
from app.models import UserRole, UserSession
from app.schemas.auth import (
    AuthLoginRequest,
    AuthSessionResponse,
    AuthSignupRequest,
)
from app.services.auth import (
    AuthConfig,
    AuthenticationNotConfiguredError,
    InvalidCredentialsError,
    InvalidPasswordError,
    LoginResult,
    UsernameUnavailableError,
    login_user,
    revoke_user_session,
    signup_user,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(
    response: Response,
    result: LoginResult,
    config: AuthConfig,
) -> None:
    cookie_options = {
        "secure": config.cookie_secure,
        "samesite": "lax",
        "path": "/",
        "max_age": config.session_ttl_seconds,
        "expires": result.user_session.expires_at,
    }
    response.set_cookie(
        SESSION_COOKIE_NAME,
        result.session_token,
        httponly=True,
        **cookie_options,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        result.csrf_token,
        httponly=False,
        **cookie_options,
    )


def _clear_auth_cookies(response: Response, config: AuthConfig) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=config.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=config.cookie_secure,
        httponly=False,
        samesite="lax",
    )


def _session_response(
    user_session: UserSession,
    config: AuthConfig,
) -> AuthSessionResponse:
    return AuthSessionResponse(
        username=user_session.user.username,
        role=user_session.user.role,
        watchlist_limit=(
            None
            if user_session.user.role == UserRole.ADMIN
            else config.normal_user_watchlist_limit
        ),
        expires_at=user_session.expires_at,
    )


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    request: AuthLoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_auth_db_session)],
    config: Annotated[AuthConfig, Depends(get_auth_config)],
) -> AuthSessionResponse:
    try:
        result = await login_user(
            session,
            config,
            request.username,
            request.password.get_secret_value(),
        )
    except AuthenticationNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_NOT_CONFIGURED",
        ) from error
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS",
        ) from error

    _set_auth_cookies(response, result, config)
    return _session_response(result.user_session, config)


@router.post(
    "/signup",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    request: AuthSignupRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_auth_db_session)],
    config: Annotated[AuthConfig, Depends(get_auth_config)],
) -> AuthSessionResponse:
    try:
        result = await signup_user(
            session,
            config,
            request.username,
            request.password.get_secret_value(),
        )
    except UsernameUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="USERNAME_UNAVAILABLE",
        ) from error
    except InvalidPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="PASSWORD_TOO_SHORT",
        ) from error

    _set_auth_cookies(response, result, config)
    return _session_response(result.user_session, config)


@router.get("/session", response_model=AuthSessionResponse)
def read_session(
    user_session: Annotated[UserSession, Depends(require_user_session)],
    config: Annotated[AuthConfig, Depends(get_auth_config)],
) -> AuthSessionResponse:
    return _session_response(user_session, config)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_auth_db_session)],
    config: Annotated[AuthConfig, Depends(get_auth_config)],
    user_session: Annotated[UserSession, Depends(require_user_csrf)],
) -> None:
    await revoke_user_session(session, user_session)
    _clear_auth_cookies(response, config)
