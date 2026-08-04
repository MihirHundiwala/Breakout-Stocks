from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, UserRole
from app.services.admin_analytics import get_admin_analytics


NOW = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_admin_analytics_counts_registration_and_activity_windows(
    db_session: AsyncSession,
) -> None:
    db_session.add_all(
        [
            AppUser(
                username="active-week",
                role=UserRole.USER,
                password_hash="$argon2-test",
                created_at=NOW - timedelta(days=3),
                updated_at=NOW - timedelta(days=3),
                last_active_at=NOW - timedelta(days=1),
            ),
            AppUser(
                username="active-month",
                role=UserRole.USER,
                password_hash="$argon2-test",
                created_at=NOW - timedelta(days=20),
                updated_at=NOW - timedelta(days=20),
                last_active_at=NOW - timedelta(days=10),
            ),
            AppUser(
                username="old-user",
                role=UserRole.USER,
                password_hash="$argon2-test",
                created_at=NOW - timedelta(days=60),
                updated_at=NOW - timedelta(days=60),
                last_active_at=NOW - timedelta(days=40),
            ),
        ]
    )
    await db_session.commit()

    result = await get_admin_analytics(db_session, occurred_at=NOW)

    assert result.users.registered_users == 3
    assert result.users.new_users_7d == 1
    assert result.users.new_users_30d == 2
    assert result.users.active_users_7d == 1
    assert result.users.active_users_30d == 2
    assert result.stocks.tracked_stocks == 0
    assert result.jobs.pending_jobs == 0
