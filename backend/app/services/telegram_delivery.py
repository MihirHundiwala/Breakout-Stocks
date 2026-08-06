from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AnalysisChartSnapshot,
    AnalysisSnapshot,
    Company,
    Instrument,
    TechnicalStatus,
    TelegramNotification,
    TelegramNotificationStatus,
    TelegramConnection,
    UserWatchlistItem,
)
from app.providers.telegram import (
    TelegramDeliveryError,
    TelegramPhoto,
)
from app.services.telegram_chart import render_setup_chart_png


class TelegramSender(Protocol):
    async def send_alert(
        self,
        *,
        chat_id: str,
        caption: str,
        photos: list[TelegramPhoto],
    ) -> None: ...


class TelegramDeliveryOutcome(StrEnum):
    NO_NOTIFICATION = "NO_NOTIFICATION"
    SENT = "SENT"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ClaimedTelegramNotification:
    notification_id: int
    analysis_snapshot_id: int
    attempt_count: int


@dataclass(frozen=True, slots=True)
class TelegramDeliveryResult:
    outcome: TelegramDeliveryOutcome
    notification_id: int | None


@dataclass(frozen=True, slots=True)
class TelegramNotificationMaterial:
    chat_id: str
    company_name: str
    trading_symbol: str
    snapshot: AnalysisSnapshot
    previous_snapshot: AnalysisSnapshot | None
    charts: list[AnalysisChartSnapshot]
    event_kind: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def claim_next_telegram_notification(
    session: AsyncSession,
    *,
    occurred_at: datetime,
) -> ClaimedTelegramNotification | None:
    async with session.begin():
        notification = await session.scalar(
            select(TelegramNotification)
            .where(
                TelegramNotification.status
                == TelegramNotificationStatus.PENDING,
                TelegramNotification.next_attempt_at <= occurred_at,
            )
            .order_by(
                TelegramNotification.next_attempt_at,
                TelegramNotification.created_at,
                TelegramNotification.id,
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if notification is None:
            return None
        notification.status = TelegramNotificationStatus.RUNNING
        notification.started_at = occurred_at
        notification.attempt_count += 1
        await session.flush()
        return ClaimedTelegramNotification(
            notification_id=notification.id,
            analysis_snapshot_id=notification.analysis_snapshot_id,
            attempt_count=notification.attempt_count,
        )


async def _load_material(
    session: AsyncSession,
    notification_id: int,
) -> TelegramNotificationMaterial | None:
    row = (
        await session.execute(
            select(
                TelegramNotification,
                AnalysisSnapshot,
                Instrument,
                Company,
                TelegramConnection,
            )
            .join(
                AnalysisSnapshot,
                AnalysisSnapshot.id
                == TelegramNotification.analysis_snapshot_id,
            )
            .join(Instrument, Instrument.id == AnalysisSnapshot.instrument_id)
            .join(Company, Company.id == Instrument.company_id)
            .join(
                TelegramConnection,
                TelegramConnection.user_id == TelegramNotification.user_id,
            )
            .join(
                UserWatchlistItem,
                (
                    UserWatchlistItem.user_id
                    == TelegramNotification.user_id
                )
                & (
                    UserWatchlistItem.instrument_id
                    == AnalysisSnapshot.instrument_id
                ),
            )
            .where(
                TelegramNotification.id == notification_id,
                UserWatchlistItem.is_active.is_(True),
            )
        )
    ).one_or_none()
    if row is None:
        return None
    notification, snapshot, instrument, company, connection = row
    if connection.telegram_chat_id is None:
        return None
    previous_snapshot = None
    if notification.previous_analysis_snapshot_id is not None:
        previous_snapshot = await session.get(
            AnalysisSnapshot,
            notification.previous_analysis_snapshot_id,
        )
    charts = list(
        await session.scalars(
            select(AnalysisChartSnapshot)
            .where(
                AnalysisChartSnapshot.analysis_snapshot_id == snapshot.id
            )
            .order_by(AnalysisChartSnapshot.timeframe)
        )
    )
    return TelegramNotificationMaterial(
        chat_id=connection.telegram_chat_id,
        company_name=company.name,
        trading_symbol=instrument.trading_symbol,
        snapshot=snapshot,
        previous_snapshot=previous_snapshot,
        charts=charts,
        event_kind=notification.event_kind,
    )


def _status_label(value: object) -> str:
    raw = getattr(value, "value", str(value))
    if str(raw) == TechnicalStatus.BREAKOUT.value:
        return "Strong Breakout"
    return str(raw).replace("_", " ").title()


def _caption(material: TelegramNotificationMaterial) -> str:
    snapshot = material.snapshot
    previous = material.previous_snapshot
    change = (
        ((snapshot.close_price / snapshot.previous_close_price) - Decimal("1"))
        * Decimal("100")
    )
    current_status = _status_label(snapshot.technical_status)
    if material.event_kind == "WATCHLIST_ADDED":
        transition = f"Added to watchlist - current setup: {current_status}"
    elif previous is not None and previous.technical_status != snapshot.technical_status:
        transition = (
            f"{_status_label(previous.technical_status)} -> {current_status}"
        )
    else:
        transition = f"{current_status} (setup structure changed)"
    timeframes = ", ".join(chart.timeframe.title() for chart in material.charts)
    lines = [
        f"{material.company_name} ({material.trading_symbol})",
        transition,
        f"As of: {snapshot.analysis_date.strftime('%d %b %Y')}",
        f"Close: INR {snapshot.close_price:,.2f} ({change:+.2f}%)",
    ]
    if timeframes:
        lines.append(f"Charts: {timeframes}")
    elif snapshot.technical_status.value == "NO_SETUP":
        lines.append("The previous setup is no longer valid.")
    return "\n".join(lines)


async def _mark_sent(
    session: AsyncSession,
    notification_id: int,
) -> None:
    async with session.begin():
        notification = await session.get(
            TelegramNotification,
            notification_id,
            with_for_update=True,
        )
        if notification is not None:
            await session.delete(notification)


async def _mark_failed_or_retry(
    session: AsyncSession,
    notification_id: int,
    *,
    occurred_at: datetime,
    error: TelegramDeliveryError,
    attempt_count: int,
    maximum_attempts: int,
    retry_base_seconds: int,
) -> TelegramDeliveryOutcome:
    async with session.begin():
        notification = await session.get(
            TelegramNotification,
            notification_id,
            with_for_update=True,
        )
        if notification is None:
            return TelegramDeliveryOutcome.FAILED
        if error.retryable and attempt_count < maximum_attempts:
            exponential_delay = min(
                retry_base_seconds * (2 ** (attempt_count - 1)),
                15 * 60,
            )
            delay = max(error.retry_after_seconds or 0, exponential_delay)
            notification.status = TelegramNotificationStatus.PENDING
            notification.next_attempt_at = occurred_at + timedelta(seconds=delay)
            notification.started_at = None
            notification.error_code = None
            notification.error_message = None
            return TelegramDeliveryOutcome.RETRY_SCHEDULED
        notification.status = TelegramNotificationStatus.FAILED
        notification.failed_at = occurred_at
        notification.error_code = error.code
        notification.error_message = (
            "Telegram could not deliver this setup notification."
        )
        return TelegramDeliveryOutcome.FAILED


async def process_one_telegram_notification(
    session_factory: async_sessionmaker[AsyncSession],
    sender: TelegramSender,
    *,
    clock: Callable[[], datetime] = _utc_now,
    maximum_attempts: int = 3,
    retry_base_seconds: int = 60,
) -> TelegramDeliveryResult:
    async with session_factory() as session:
        claimed = await claim_next_telegram_notification(
            session,
            occurred_at=clock(),
        )
    if claimed is None:
        return TelegramDeliveryResult(
            TelegramDeliveryOutcome.NO_NOTIFICATION,
            None,
        )
    try:
        async with session_factory() as session:
            material = await _load_material(session, claimed.notification_id)
        if material is None:
            async with session_factory() as session:
                await _mark_sent(session, claimed.notification_id)
            return TelegramDeliveryResult(
                TelegramDeliveryOutcome.SENT,
                claimed.notification_id,
            )
        photos = [
            TelegramPhoto(
                filename=(
                    f"{material.trading_symbol.lower()}-"
                    f"{chart.timeframe.lower()}.png"
                ),
                content=render_setup_chart_png(
                    company_name=material.company_name,
                    trading_symbol=material.trading_symbol,
                    snapshot=material.snapshot,
                    chart=chart,
                ),
            )
            for chart in material.charts
        ]
        await sender.send_alert(
            chat_id=material.chat_id,
            caption=_caption(material),
            photos=photos,
        )
    except TelegramDeliveryError as error:
        decision_time = clock()
        async with session_factory() as session:
            outcome = await _mark_failed_or_retry(
                session,
                claimed.notification_id,
                occurred_at=decision_time,
                error=error,
                attempt_count=claimed.attempt_count,
                maximum_attempts=maximum_attempts,
                retry_base_seconds=retry_base_seconds,
            )
        return TelegramDeliveryResult(outcome, claimed.notification_id)
    except Exception:
        decision_time = clock()
        async with session_factory() as session:
            outcome = await _mark_failed_or_retry(
                session,
                claimed.notification_id,
                occurred_at=decision_time,
                error=TelegramDeliveryError(
                    "TELEGRAM_RENDER_OR_DELIVERY_ERROR",
                    retryable=False,
                ),
                attempt_count=claimed.attempt_count,
                maximum_attempts=maximum_attempts,
                retry_base_seconds=retry_base_seconds,
            )
        return TelegramDeliveryResult(outcome, claimed.notification_id)
    async with session_factory() as session:
        await _mark_sent(session, claimed.notification_id)
    return TelegramDeliveryResult(
        TelegramDeliveryOutcome.SENT,
        claimed.notification_id,
    )


async def recover_stale_telegram_notifications(
    session: AsyncSession,
    *,
    stale_before: datetime,
    occurred_at: datetime,
) -> int:
    recovered = 0
    async with session.begin():
        notifications = list(
            await session.scalars(
                select(TelegramNotification)
                .where(
                    TelegramNotification.status
                    == TelegramNotificationStatus.RUNNING,
                    TelegramNotification.started_at < stale_before,
                )
                .with_for_update(skip_locked=True)
            )
        )
        for notification in notifications:
            notification.status = TelegramNotificationStatus.PENDING
            notification.started_at = None
            notification.next_attempt_at = occurred_at
            recovered += 1
    return recovered


async def active_telegram_notification_count(session: AsyncSession) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(TelegramNotification)
        .where(
            TelegramNotification.status.in_(
                (
                    TelegramNotificationStatus.PENDING,
                    TelegramNotificationStatus.RUNNING,
                )
            )
        )
    )
    return int(value or 0)
