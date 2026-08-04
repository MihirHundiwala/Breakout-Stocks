from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AppUser,
    Company,
    Instrument,
    TrackedInstrument,
    TrackingOperationalState,
    UserRole,
    UserWatchlistItem,
)


NOW = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
BASELINE_SESSION = date(2026, 7, 24)


def normal_user(username: str) -> AppUser:
    return AppUser(
        username=username,
        role=UserRole.USER,
        password_hash="$argon2id$synthetic-test-hash",
        created_at=NOW,
        updated_at=NOW,
    )


def instrument() -> Instrument:
    return Instrument(
        company=Company(name="Shared Research Limited"),
        exchange="NSE",
        trading_symbol="SHARED",
    )


@pytest.mark.anyio
async def test_two_users_share_one_instrument_and_tracking_record(
    db_session: AsyncSession,
) -> None:
    shared_instrument = instrument()
    first_user = normal_user("first-user")
    second_user = normal_user("second-user")
    tracking = TrackedInstrument(
        instrument=shared_instrument,
        operational_state=TrackingOperationalState.READY,
        target_session=date(2026, 7, 24),
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add_all(
        [
            tracking,
            UserWatchlistItem(
                user=first_user,
                instrument=shared_instrument,
                baseline_session=BASELINE_SESSION,
            ),
            UserWatchlistItem(
                user=second_user,
                instrument=shared_instrument,
                baseline_session=BASELINE_SESSION,
            ),
        ]
    )

    await db_session.flush()

    assert len(shared_instrument.user_watchlist_items) == 2
    assert shared_instrument.tracked_instrument is tracking


@pytest.mark.anyio
async def test_user_cannot_have_duplicate_membership(
    db_session: AsyncSession,
) -> None:
    shared_instrument = instrument()
    user = normal_user("duplicate-test")
    db_session.add_all(
        [
            UserWatchlistItem(
                user=user,
                instrument=shared_instrument,
                baseline_session=BASELINE_SESSION,
            ),
            UserWatchlistItem(
                user=user,
                instrument=shared_instrument,
                baseline_session=BASELINE_SESSION,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_inactive_membership_requires_deactivation_time(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        UserWatchlistItem(
            user=normal_user("inactive-test"),
            instrument=instrument(),
            is_active=False,
            baseline_session=BASELINE_SESSION,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_baseline_close_must_be_positive(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        UserWatchlistItem(
            user=normal_user("invalid-baseline"),
            instrument=instrument(),
            baseline_session=BASELINE_SESSION,
            baseline_close_price=0,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_normal_user_requires_password_hash(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        AppUser(
            username="missing-password",
            role=UserRole.USER,
            password_hash=None,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()
