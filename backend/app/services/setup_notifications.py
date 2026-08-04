from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import desc, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisChartSnapshot,
    AnalysisSnapshot,
    AppUser,
    TechnicalStatus,
    TelegramNotification,
    TelegramNotificationStatus,
    TelegramConnection,
    UserWatchlistItem,
)


MATERIAL_RESISTANCE_CHANGE = Decimal("0.005")


@dataclass(frozen=True, slots=True)
class PreviousSetupState:
    snapshot_id: int
    status: TechnicalStatus
    generated_at: datetime
    resistance_by_timeframe: dict[str, Decimal]


async def get_previous_setup_state(
    session: AsyncSession,
    *,
    instrument_id: int,
) -> PreviousSetupState | None:
    snapshot = await session.scalar(
        select(AnalysisSnapshot)
        .where(AnalysisSnapshot.instrument_id == instrument_id)
        .order_by(
            desc(AnalysisSnapshot.analysis_date),
            desc(AnalysisSnapshot.generated_at),
            desc(AnalysisSnapshot.id),
        )
        .limit(1)
    )
    if snapshot is None:
        return None
    charts = list(
        await session.scalars(
            select(AnalysisChartSnapshot).where(
                AnalysisChartSnapshot.analysis_snapshot_id == snapshot.id
            )
        )
    )
    return PreviousSetupState(
        snapshot_id=snapshot.id,
        status=snapshot.technical_status,
        generated_at=snapshot.generated_at,
        resistance_by_timeframe={
            chart.timeframe: chart.resistance_zone_upper for chart in charts
        },
    )


def setup_change_kind(
    previous: PreviousSetupState | None,
    *,
    current_status: TechnicalStatus,
    current_resistance_by_timeframe: dict[str, Decimal],
) -> str | None:
    if previous is None:
        return None
    if previous.status != current_status:
        return "STATUS_CHANGED"
    if (
        previous.resistance_by_timeframe.keys()
        != current_resistance_by_timeframe.keys()
    ):
        return "SETUP_STRUCTURE_CHANGED"
    for timeframe, current_resistance in current_resistance_by_timeframe.items():
        previous_resistance = previous.resistance_by_timeframe[timeframe]
        if previous_resistance <= 0:
            return "SETUP_STRUCTURE_CHANGED"
        change = abs(current_resistance - previous_resistance) / previous_resistance
        if change >= MATERIAL_RESISTANCE_CHANGE:
            return "SETUP_STRUCTURE_CHANGED"
    return None


async def enqueue_setup_change_notification(
    session: AsyncSession,
    *,
    snapshot_id: int,
    previous: PreviousSetupState | None,
    current_status: TechnicalStatus,
    chart_values: list[dict[str, object]],
    created_at: datetime,
    excluded_user_ids: set[int] | None = None,
) -> int:
    current_resistance = {
        str(chart["timeframe"]): Decimal(str(chart["resistance_zone_upper"]))
        for chart in chart_values
    }
    event_kind = setup_change_kind(
        previous,
        current_status=current_status,
        current_resistance_by_timeframe=current_resistance,
    )
    if event_kind is None:
        return 0
    followers = (
        select(TelegramConnection.user_id)
            .join(AppUser, AppUser.id == TelegramConnection.user_id)
            .join(
                UserWatchlistItem,
                UserWatchlistItem.user_id == TelegramConnection.user_id,
            )
            .where(
                UserWatchlistItem.instrument_id == (
                    select(AnalysisSnapshot.instrument_id)
                    .where(AnalysisSnapshot.id == snapshot_id)
                    .scalar_subquery()
                ),
                UserWatchlistItem.is_active.is_(True),
                AppUser.is_active.is_(True),
                TelegramConnection.telegram_chat_id.is_not(None),
            )
    )
    if excluded_user_ids:
        followers = followers.where(
            TelegramConnection.user_id.not_in(excluded_user_ids)
        )
    user_ids = list(await session.scalars(followers))
    inserted_count = 0
    for user_id in user_ids:
        inserted_id = await session.scalar(
            insert(TelegramNotification)
            .values(
                user_id=user_id,
                analysis_snapshot_id=snapshot_id,
                previous_analysis_snapshot_id=(
                    previous.snapshot_id if previous is not None else None
                ),
                event_kind=event_kind,
                status=TelegramNotificationStatus.PENDING,
                attempt_count=0,
                created_at=created_at,
                next_attempt_at=created_at,
            )
            .on_conflict_do_nothing(
                constraint="uq_telegram_notification_user_analysis_snapshot"
            )
            .returning(TelegramNotification.id)
        )
        inserted_count += inserted_id is not None
    return inserted_count


async def _enqueue_watchlist_added(
    session: AsyncSession,
    *,
    user_id: int,
    snapshot_id: int,
    created_at: datetime,
) -> bool:
    inserted_id = await session.scalar(
        insert(TelegramNotification)
        .values(
            user_id=user_id,
            analysis_snapshot_id=snapshot_id,
            previous_analysis_snapshot_id=None,
            event_kind="WATCHLIST_ADDED",
            status=TelegramNotificationStatus.PENDING,
            attempt_count=0,
            created_at=created_at,
            next_attempt_at=created_at,
        )
        .on_conflict_do_nothing(
            constraint="uq_telegram_notification_user_analysis_snapshot"
        )
        .returning(TelegramNotification.id)
    )
    return inserted_id is not None


async def enqueue_existing_watchlist_setup_notification(
    session: AsyncSession,
    *,
    user_id: int,
    instrument_id: int,
    target_session: date,
    created_at: datetime,
) -> bool:
    """Queue a fresh stored setup and report whether analysis was available."""
    snapshot = await session.scalar(
        select(AnalysisSnapshot)
        .where(
            AnalysisSnapshot.instrument_id == instrument_id,
            AnalysisSnapshot.analysis_date == target_session,
        )
        .order_by(
            desc(AnalysisSnapshot.generated_at),
            desc(AnalysisSnapshot.id),
        )
        .limit(1)
    )
    if snapshot is None:
        return False
    if snapshot.technical_status == TechnicalStatus.NO_SETUP:
        return True
    connected_user_id = await session.scalar(
        select(TelegramConnection.user_id).where(
            TelegramConnection.user_id == user_id,
            TelegramConnection.telegram_chat_id.is_not(None),
        )
    )
    if connected_user_id is not None:
        await _enqueue_watchlist_added(
            session,
            user_id=user_id,
            snapshot_id=snapshot.id,
            created_at=created_at,
        )
    return True


async def enqueue_pending_watchlist_setup_notifications(
    session: AsyncSession,
    *,
    snapshot_id: int,
    current_status: TechnicalStatus,
    created_at: datetime,
) -> set[int]:
    """Consume pending first-analysis decisions and queue valid setups."""
    memberships = list(
        await session.scalars(
            select(UserWatchlistItem)
            .where(
                UserWatchlistItem.instrument_id
                == select(AnalysisSnapshot.instrument_id)
                .where(AnalysisSnapshot.id == snapshot_id)
                .scalar_subquery(),
                UserWatchlistItem.is_active.is_(True),
                UserWatchlistItem.telegram_setup_alert_pending.is_(True),
            )
            .with_for_update()
        )
    )
    user_ids = {membership.user_id for membership in memberships}
    if user_ids and current_status != TechnicalStatus.NO_SETUP:
        connected_user_ids = set(
            await session.scalars(
                select(TelegramConnection.user_id).where(
                    TelegramConnection.user_id.in_(user_ids),
                    TelegramConnection.telegram_chat_id.is_not(None),
                )
            )
        )
        for user_id in connected_user_ids:
            await _enqueue_watchlist_added(
                session,
                user_id=user_id,
                snapshot_id=snapshot_id,
                created_at=created_at,
            )
    if memberships:
        await session.execute(
            update(UserWatchlistItem)
            .where(
                UserWatchlistItem.id.in_(
                    membership.id for membership in memberships
                )
            )
            .values(
                telegram_setup_alert_pending=False,
                updated_at=created_at,
            )
        )
    return user_ids
