from base64 import b64decode, b64encode
from binascii import Error as Base64DecodeError
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import re
import secrets

from pydantic import SecretStr
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, UserRole, UserSession
from app.repositories.user_sessions import get_active_user_session
from app.repositories.users import get_admin_user_for_update, get_user_by_username


SESSION_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32
MINIMUM_PASSWORD_LENGTH = 12
MINIMUM_USERNAME_LENGTH = 3
USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")

password_hash = PasswordHash.recommended()
dummy_password_hash = password_hash.hash("timing-check-only")


class AuthServiceError(Exception):
    """Base class for expected authentication failures."""


class AuthenticationNotConfiguredError(AuthServiceError):
    pass


class InvalidCredentialsError(AuthServiceError):
    pass


class AuthenticationRequiredError(AuthServiceError):
    pass


class CsrfValidationError(AuthServiceError):
    pass


class UsernameUnavailableError(AuthServiceError):
    pass


class InvalidPasswordError(AuthServiceError):
    pass


@dataclass(frozen=True, slots=True)
class AuthConfig:
    admin_username: str
    admin_password_hash_b64: SecretStr | None
    session_ttl_seconds: int
    cookie_secure: bool
    normal_user_watchlist_limit: int


@dataclass(frozen=True, slots=True)
class LoginResult:
    user_session: UserSession
    session_token: str
    csrf_token: str


def _event_time(value: datetime | None) -> datetime:
    event_time = value or datetime.now(UTC)
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise ValueError("Event timestamps must be timezone-aware.")
    return event_time.astimezone(UTC)


def _token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def normalize_username(username: str) -> str:
    return username.strip().lower()


def _configured_admin_password_hash(config: AuthConfig) -> str:
    if config.admin_password_hash_b64 is None:
        raise AuthenticationNotConfiguredError
    encoded_hash = config.admin_password_hash_b64.get_secret_value().strip()
    if not encoded_hash:
        raise AuthenticationNotConfiguredError
    try:
        decoded_hash = b64decode(encoded_hash, validate=True).decode("utf-8")
    except (Base64DecodeError, UnicodeDecodeError, ValueError) as error:
        raise AuthenticationNotConfiguredError from error
    if not decoded_hash.startswith("$argon2"):
        raise AuthenticationNotConfiguredError
    return decoded_hash


def hash_admin_password_to_base64(password: str) -> str:
    return b64encode(password_hash.hash(password).encode("utf-8")).decode("ascii")


def hash_normal_user_password(password: str) -> str:
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise InvalidPasswordError
    return password_hash.hash(password)


def _password_is_valid(password: str, encoded_hash: str) -> bool:
    try:
        return password_hash.verify(password, encoded_hash)
    except (TypeError, ValueError, UnknownHashError) as error:
        raise AuthenticationNotConfiguredError from error


async def _sync_admin_identity(
    session: AsyncSession,
    config: AuthConfig,
) -> None:
    async with session.begin():
        admin = await get_admin_user_for_update(session)
        if admin is None:
            session.add(
                AppUser(
                    username=config.admin_username,
                    role=UserRole.ADMIN,
                    password_hash=None,
                )
            )
        else:
            admin.username = config.admin_username


async def login_user(
    session: AsyncSession,
    config: AuthConfig,
    username: str,
    password: str,
    *,
    occurred_at: datetime | None = None,
) -> LoginResult:
    event_time = _event_time(occurred_at)
    await _sync_admin_identity(session, config)
    normalized_username = normalize_username(username)
    user = await get_user_by_username(session, normalized_username)
    await session.commit()

    if user is None or not user.is_active:
        _password_is_valid(password, dummy_password_hash)
        raise InvalidCredentialsError

    if user.role == UserRole.ADMIN:
        encoded_hash = _configured_admin_password_hash(config)
    elif user.password_hash is not None:
        encoded_hash = user.password_hash
    else:
        raise AuthenticationNotConfiguredError

    if not _password_is_valid(password, encoded_hash):
        raise InvalidCredentialsError

    session_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    csrf_token = secrets.token_urlsafe(CSRF_TOKEN_BYTES)
    current_user = await session.scalar(
        select(AppUser)
        .where(AppUser.id == user.id, AppUser.is_active.is_(True))
        .with_for_update()
    )
    if current_user is None:
        await session.rollback()
        raise InvalidCredentialsError
    current_user.last_active_at = event_time
    user_session = UserSession(
        user=current_user,
        token_digest=_token_digest(session_token),
        csrf_token_digest=_token_digest(csrf_token),
        created_at=event_time,
        expires_at=event_time + timedelta(seconds=config.session_ttl_seconds),
    )
    session.add(user_session)
    await session.commit()

    return LoginResult(
        user_session=user_session,
        session_token=session_token,
        csrf_token=csrf_token,
    )


async def authenticate_user_session(
    session: AsyncSession,
    session_token: str | None,
    *,
    occurred_at: datetime | None = None,
) -> UserSession:
    if not session_token:
        raise AuthenticationRequiredError
    user_session = await get_active_user_session(
        session,
        _token_digest(session_token),
        _event_time(occurred_at),
    )
    if user_session is None:
        raise AuthenticationRequiredError
    return user_session


async def record_authenticated_activity(
    session: AsyncSession,
    user_session: UserSession,
    *,
    occurred_at: datetime | None = None,
    minimum_interval: timedelta = timedelta(minutes=15),
) -> None:
    event_time = _event_time(occurred_at)
    last_active_at = user_session.user.last_active_at
    if (
        last_active_at is not None
        and last_active_at >= event_time - minimum_interval
    ):
        return
    await session.execute(
        update(AppUser)
        .where(
            AppUser.id == user_session.user_id,
            (
                AppUser.last_active_at.is_(None)
                | (
                    AppUser.last_active_at
                    < event_time - minimum_interval
                )
            ),
        )
        .values(last_active_at=event_time)
    )
    await session.commit()
    user_session.user.last_active_at = event_time


def validate_csrf_token(
    user_session: UserSession,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> None:
    if not csrf_cookie or not csrf_header:
        raise CsrfValidationError
    if not secrets.compare_digest(csrf_cookie, csrf_header):
        raise CsrfValidationError
    if not secrets.compare_digest(
        _token_digest(csrf_header),
        user_session.csrf_token_digest,
    ):
        raise CsrfValidationError


async def revoke_user_session(
    session: AsyncSession,
    user_session: UserSession,
    *,
    occurred_at: datetime | None = None,
) -> None:
    user_session.revoked_at = _event_time(occurred_at)
    await session.commit()


async def create_normal_user(
    session: AsyncSession,
    username: str,
    password: str,
    *,
    reserved_username: str | None = None,
) -> AppUser:
    normalized_username = normalize_username(username)
    if (
        len(normalized_username) < MINIMUM_USERNAME_LENGTH
        or len(normalized_username) > 64
        or USERNAME_PATTERN.fullmatch(normalized_username) is None
        or normalized_username == normalize_username(reserved_username or "")
    ):
        raise UsernameUnavailableError
    encoded_hash = hash_normal_user_password(password)
    try:
        async with session.begin():
            existing = await get_user_by_username(session, normalized_username)
            if existing is not None:
                raise UsernameUnavailableError
            user = AppUser(
                username=normalized_username,
                role=UserRole.USER,
                password_hash=encoded_hash,
            )
            session.add(user)
            await session.flush()
    except IntegrityError as error:
        # The database unique constraint closes the concurrent-signup race.
        raise UsernameUnavailableError from error
    return user


async def signup_user(
    session: AsyncSession,
    config: AuthConfig,
    username: str,
    password: str,
) -> LoginResult:
    user = await create_normal_user(
        session,
        username,
        password,
        reserved_username=config.admin_username,
    )
    return await login_user(session, config, user.username, password)


# Compatibility names for the existing test/API boundary during migration.
AdminAuthConfig = AuthConfig
login_admin = login_user
authenticate_admin_session = authenticate_user_session
revoke_admin_session = revoke_user_session
