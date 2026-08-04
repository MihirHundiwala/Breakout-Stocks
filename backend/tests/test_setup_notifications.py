from decimal import Decimal
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisSnapshot,
    AppUser,
    Company,
    FundamentalCoverageStatus,
    Instrument,
    TechnicalStatus,
    TelegramConnection,
    TelegramNotification,
    UserRole,
    UserWatchlistItem,
)
from app.services.setup_notifications import (
    PreviousSetupState,
    enqueue_pending_watchlist_setup_notifications,
    enqueue_setup_change_notification,
    setup_change_kind,
)


def state(
    status: TechnicalStatus,
    charts: dict[str, str],
) -> PreviousSetupState:
    return PreviousSetupState(
        snapshot_id=1,
        status=status,
        generated_at=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
        resistance_by_timeframe={
            key: Decimal(value) for key, value in charts.items()
        },
    )


def test_first_snapshot_and_unchanged_setup_are_silent() -> None:
    assert setup_change_kind(
        None,
        current_status=TechnicalStatus.BREAKOUT,
        current_resistance_by_timeframe={"DAILY": Decimal("100")},
    ) is None
    assert setup_change_kind(
        state(TechnicalStatus.CONSOLIDATING, {"DAILY": "100"}),
        current_status=TechnicalStatus.CONSOLIDATING,
        current_resistance_by_timeframe={"DAILY": Decimal("100.49")},
    ) is None


def test_status_timeframe_and_material_resistance_changes_notify() -> None:
    previous = state(TechnicalStatus.CONSOLIDATING, {"DAILY": "100"})
    assert setup_change_kind(
        previous,
        current_status=TechnicalStatus.BREAKOUT,
        current_resistance_by_timeframe={"DAILY": Decimal("100")},
    ) == "STATUS_CHANGED"
    assert setup_change_kind(
        state(TechnicalStatus.BREAKOUT, {"DAILY": "100"}),
        current_status=TechnicalStatus.NO_SETUP,
        current_resistance_by_timeframe={},
    ) == "STATUS_CHANGED"
    assert setup_change_kind(
        previous,
        current_status=TechnicalStatus.CONSOLIDATING,
        current_resistance_by_timeframe={
            "DAILY": Decimal("100"),
            "WEEKLY": Decimal("120"),
        },
    ) == "SETUP_STRUCTURE_CHANGED"
    assert setup_change_kind(
        previous,
        current_status=TechnicalStatus.CONSOLIDATING,
        current_resistance_by_timeframe={"DAILY": Decimal("100.50")},
    ) == "SETUP_STRUCTURE_CHANGED"


@pytest.mark.anyio
async def test_outbox_targets_only_connected_active_follower(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    followed_user = AppUser(
        username="followed-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    unrelated_user = AppUser(
        username="unrelated-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    inactive_user = AppUser(
        username="inactive-follower",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
        is_active=False,
    )
    instrument = Instrument(
        company=Company(name="Notification Industries Limited"),
        exchange="NSE",
        trading_symbol="NOTIFY",
    )
    db_session.add_all((followed_user, unrelated_user, inactive_user, instrument))
    await db_session.flush()
    db_session.add_all((
        TelegramConnection(
            user_id=followed_user.id,
            telegram_chat_id="101",
            telegram_username="follower",
            connected_at=now,
            updated_at=now,
        ),
        TelegramConnection(
            user_id=unrelated_user.id,
            telegram_chat_id="202",
            telegram_username="unrelated",
            connected_at=now,
            updated_at=now,
        ),
        TelegramConnection(
            user_id=inactive_user.id,
            telegram_chat_id="303",
            telegram_username="inactive",
            connected_at=now,
            updated_at=now,
        ),
        UserWatchlistItem(
            user_id=followed_user.id,
            instrument_id=instrument.id,
            baseline_session=date(2026, 7, 29),
            created_at=now,
            updated_at=now,
        ),
        UserWatchlistItem(
            user_id=inactive_user.id,
            instrument_id=instrument.id,
            baseline_session=date(2026, 7, 29),
            created_at=now,
            updated_at=now,
        ),
    ))
    previous_snapshot = AnalysisSnapshot(
        instrument_id=instrument.id,
        analysis_date=date(2026, 7, 29),
        technical_status=TechnicalStatus.CONSOLIDATING,
        fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
        close_price=Decimal("99"),
        previous_close_price=Decimal("98"),
        source="UPSTOX",
        source_fetched_at=now,
        algorithm_version="technical-v15",
        candle_revision="previous",
        generated_at=now,
    )
    current_snapshot = AnalysisSnapshot(
        instrument_id=instrument.id,
        analysis_date=date(2026, 7, 30),
        technical_status=TechnicalStatus.BREAKOUT,
        fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
        close_price=Decimal("105"),
        previous_close_price=Decimal("99"),
        source="UPSTOX",
        source_fetched_at=now,
        algorithm_version="technical-v15",
        candle_revision="current",
        generated_at=now,
    )
    db_session.add_all((previous_snapshot, current_snapshot))
    await db_session.flush()

    count = await enqueue_setup_change_notification(
        db_session,
        snapshot_id=current_snapshot.id,
        previous=PreviousSetupState(
            snapshot_id=previous_snapshot.id,
            status=TechnicalStatus.CONSOLIDATING,
            generated_at=previous_snapshot.generated_at,
            resistance_by_timeframe={"DAILY": Decimal("100")},
        ),
        current_status=TechnicalStatus.BREAKOUT,
        chart_values=[{
            "timeframe": "DAILY",
            "resistance_zone_upper": Decimal("100"),
        }],
        created_at=now,
    )
    await db_session.commit()

    notification = await db_session.scalar(select(TelegramNotification))
    assert count == 1
    assert notification is not None
    assert notification.user_id == followed_user.id


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "expected_count"),
    [
        (TechnicalStatus.BREAKOUT, 1),
        (TechnicalStatus.NO_SETUP, 0),
    ],
)
async def test_first_fresh_analysis_consumes_pending_watchlist_alert(
    db_session: AsyncSession,
    status: TechnicalStatus,
    expected_count: int,
) -> None:
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    user = AppUser(
        username=f"pending-{status.value.lower()}",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    instrument = Instrument(
        company=Company(name="Pending Alert Industries Limited"),
        exchange="NSE",
        trading_symbol=f"PENDING{expected_count}",
    )
    db_session.add_all((user, instrument))
    await db_session.flush()
    membership = UserWatchlistItem(
        user_id=user.id,
        instrument_id=instrument.id,
        baseline_session=date(2026, 7, 31),
        telegram_setup_alert_pending=True,
        created_at=now,
        updated_at=now,
    )
    snapshot = AnalysisSnapshot(
        instrument_id=instrument.id,
        analysis_date=date(2026, 7, 31),
        technical_status=status,
        fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
        close_price=Decimal("105"),
        previous_close_price=Decimal("100"),
        source="UPSTOX",
        source_fetched_at=now,
        algorithm_version="pending-alert-v1",
        candle_revision=f"pending-{expected_count}",
        generated_at=now,
    )
    db_session.add_all((
        membership,
        snapshot,
        TelegramConnection(
            user_id=user.id,
            telegram_chat_id=f"800{expected_count}",
            telegram_username=f"pending{expected_count}",
            connected_at=now,
            updated_at=now,
        ),
    ))
    await db_session.flush()

    consumed_user_ids = await enqueue_pending_watchlist_setup_notifications(
        db_session,
        snapshot_id=snapshot.id,
        current_status=status,
        created_at=now,
    )
    await db_session.commit()

    count = await db_session.scalar(
        select(func.count()).select_from(TelegramNotification)
    )
    assert consumed_user_ids == {user.id}
    assert membership.telegram_setup_alert_pending is False
    assert count == expected_count
