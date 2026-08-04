from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, UserRole, UserSession


CREATED_AT = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)


def build_user_session(**overrides: object) -> UserSession:
    values: dict[str, object] = {
        "user": AppUser(
            username="admin",
            role=UserRole.ADMIN,
            password_hash=None,
        ),
        "token_digest": "a" * 64,
        "csrf_token_digest": "b" * 64,
        "created_at": CREATED_AT,
        "expires_at": CREATED_AT + timedelta(hours=8),
    }
    values.update(overrides)
    return UserSession(**values)


@pytest.mark.anyio
async def test_admin_session_persists_only_digests(
    db_session: AsyncSession,
) -> None:
    admin_session = build_user_session()
    db_session.add(admin_session)
    await db_session.flush()

    assert admin_session.id is not None
    assert admin_session.revoked_at is None


@pytest.mark.anyio
async def test_admin_session_rejects_non_hex_token_digest(
    db_session: AsyncSession,
) -> None:
    db_session.add(build_user_session(token_digest="not-a-digest"))

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_admin_session_expiry_must_follow_creation(
    db_session: AsyncSession,
) -> None:
    db_session.add(build_user_session(expires_at=CREATED_AT))

    with pytest.raises(IntegrityError):
        await db_session.flush()
