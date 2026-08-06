from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisSnapshot,
    AppUser,
    Company,
    Instrument,
    TechnicalStatus,
    TelegramConnection,
    UserWatchlistItem,
)
from app.providers.contracts import ExchangeCalendarProvider
from app.providers.telegram import TelegramDeliveryError
from app.services.market_sessions import NSE_TIMEZONE


TELEGRAM_TEXT_LIMIT = 4096
MESSAGE_CONTENT_LIMIT = 3900


class MorningDigestSender(Protocol):
    async def send_message(self, *, chat_id: str, text: str) -> None: ...


@dataclass(frozen=True, slots=True)
class MorningSetup:
    company_name: str
    trading_symbol: str
    status: TechnicalStatus
    timeframe: str | None
    close_price: Decimal
    previous_close_price: Decimal
    resistance_price: Decimal | None
    setup_score: Decimal | None
    analysis_date: date


@dataclass(frozen=True, slots=True)
class MorningDigestResult:
    is_trading_day: bool
    connected_user_count: int
    delivered_user_count: int
    failed_user_count: int
    message_count: int


def _status_label(status: TechnicalStatus) -> str:
    if status == TechnicalStatus.BREAKOUT:
        return "Strong Breakout"
    return status.value.replace("_", " ").title()


def _setup_block(index: int, setup: MorningSetup) -> str:
    change = (
        (setup.close_price / setup.previous_close_price) - Decimal("1")
    ) * Decimal("100")
    timeframe = (
        setup.timeframe.title()
        if setup.timeframe
        else "Timeframe unavailable"
    )
    lines = [
        f"{index}. {setup.company_name} ({setup.trading_symbol})",
        f"{_status_label(setup.status)} - {timeframe}",
        f"Close: INR {setup.close_price:,.2f} ({change:+.2f}%)",
    ]
    if setup.resistance_price is not None:
        lines[-1] += f" | Resistance: INR {setup.resistance_price:,.2f}"
    if setup.setup_score is not None:
        lines.append(f"Setup quality: {setup.setup_score:.0f}/100")
    lines.append(f"As of: {setup.analysis_date.strftime('%d %b %Y')}")
    return "\n".join(lines)


def build_morning_digest_messages(
    *,
    trading_date: date,
    setups: list[MorningSetup],
    content_limit: int = MESSAGE_CONTENT_LIMIT,
) -> list[str]:
    heading = f"Morning watchlist setups - {trading_date.strftime('%d %b %Y')}"
    if not setups:
        return [
            f"{heading}\n\nNo current breakout setups in your watchlist."
        ]

    chunks: list[list[str]] = []
    current: list[str] = []
    current_length = len(heading) + 2
    for index, setup in enumerate(setups, start=1):
        block = _setup_block(index, setup)
        addition = len(block) + (2 if current else 0)
        if current and current_length + addition > content_limit:
            chunks.append(current)
            current = []
            current_length = len(heading) + 2
        current.append(block)
        current_length += len(block) + (2 if len(current) > 1 else 0)
    if current:
        chunks.append(current)

    total = len(chunks)
    messages = []
    for index, blocks in enumerate(chunks, start=1):
        part = f" ({index}/{total})" if total > 1 else ""
        messages.append(f"{heading}{part}\n\n" + "\n\n".join(blocks))
    if any(len(message) > TELEGRAM_TEXT_LIMIT for message in messages):
        raise ValueError("A morning digest message exceeds Telegram's text limit.")
    return messages


async def _load_connected_users(
    session: AsyncSession,
) -> dict[int, str]:
    rows = (
        await session.execute(
            select(
                TelegramConnection.user_id,
                TelegramConnection.telegram_chat_id,
            )
            .join(AppUser, AppUser.id == TelegramConnection.user_id)
            .where(
                AppUser.is_active.is_(True),
                TelegramConnection.telegram_chat_id.is_not(None),
            )
            .order_by(TelegramConnection.user_id)
        )
    ).all()
    return {user_id: chat_id for user_id, chat_id in rows if chat_id is not None}


async def _load_current_setups(
    session: AsyncSession,
    *,
    user_ids: set[int],
) -> dict[int, list[MorningSetup]]:
    if not user_ids:
        return {}
    ranked_snapshots = (
        select(
            AnalysisSnapshot.id.label("snapshot_id"),
            AnalysisSnapshot.instrument_id.label("instrument_id"),
            func.row_number()
            .over(
                partition_by=AnalysisSnapshot.instrument_id,
                order_by=(
                    desc(AnalysisSnapshot.analysis_date),
                    desc(AnalysisSnapshot.generated_at),
                    desc(AnalysisSnapshot.id),
                ),
            )
            .label("snapshot_rank"),
        )
        .subquery()
    )
    rows = (
        await session.execute(
            select(
                UserWatchlistItem.user_id,
                Company.name,
                Instrument.trading_symbol,
                AnalysisSnapshot,
            )
            .join(Instrument, Instrument.id == UserWatchlistItem.instrument_id)
            .join(Company, Company.id == Instrument.company_id)
            .join(
                ranked_snapshots,
                ranked_snapshots.c.instrument_id == Instrument.id,
            )
            .join(
                AnalysisSnapshot,
                AnalysisSnapshot.id == ranked_snapshots.c.snapshot_id,
            )
            .where(
                UserWatchlistItem.user_id.in_(user_ids),
                UserWatchlistItem.is_active.is_(True),
                ranked_snapshots.c.snapshot_rank == 1,
                AnalysisSnapshot.technical_status != TechnicalStatus.NO_SETUP,
            )
            .order_by(UserWatchlistItem.user_id, Instrument.trading_symbol)
        )
    ).all()
    by_user: dict[int, list[MorningSetup]] = {user_id: [] for user_id in user_ids}
    for user_id, company_name, trading_symbol, snapshot in rows:
        by_user[user_id].append(
            MorningSetup(
                company_name=company_name,
                trading_symbol=trading_symbol,
                status=snapshot.technical_status,
                timeframe=snapshot.consolidation_timeframe,
                close_price=snapshot.close_price,
                previous_close_price=snapshot.previous_close_price,
                resistance_price=snapshot.resistance_price,
                setup_score=snapshot.setup_score,
                analysis_date=snapshot.analysis_date,
            )
        )
    return by_user


async def send_morning_watchlist_digests(
    session: AsyncSession,
    calendar_provider: ExchangeCalendarProvider,
    sender: MorningDigestSender,
    *,
    occurred_at: datetime,
) -> MorningDigestResult:
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("occurred_at must be timezone-aware.")
    local_date = occurred_at.astimezone(NSE_TIMEZONE).date()
    market_session = await calendar_provider.get_nse_session(local_date)
    if not market_session.is_open:
        return MorningDigestResult(False, 0, 0, 0, 0)

    connected_users = await _load_connected_users(session)
    setups_by_user = await _load_current_setups(
        session,
        user_ids=set(connected_users),
    )
    delivered_users = failed_users = message_count = 0
    for user_id, chat_id in connected_users.items():
        messages = build_morning_digest_messages(
            trading_date=local_date,
            setups=setups_by_user.get(user_id, []),
        )
        try:
            for message in messages:
                await sender.send_message(chat_id=chat_id, text=message)
                message_count += 1
        except TelegramDeliveryError:
            failed_users += 1
            continue
        delivered_users += 1

    return MorningDigestResult(
        True,
        len(connected_users),
        delivered_users,
        failed_users,
        message_count,
    )
