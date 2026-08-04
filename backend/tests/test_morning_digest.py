from datetime import UTC, date, datetime
from decimal import Decimal

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
from app.providers.contracts import ExchangeSession
from app.providers.telegram import TelegramDeliveryError
from app.services.morning_digest import (
    MorningSetup,
    build_morning_digest_messages,
    send_morning_watchlist_digests,
)


NOW = datetime(2026, 8, 3, 3, 0, tzinfo=UTC)  # 08:30 IST


class FakeCalendar:
    def __init__(self, *, is_open: bool) -> None:
        self.is_open = is_open
        self.requested_dates: list[date] = []

    async def get_nse_session(self, session_date: date) -> ExchangeSession:
        self.requested_dates.append(session_date)
        return ExchangeSession(session_date=session_date, is_open=self.is_open)


class RecordingSender:
    def __init__(self, *, failing_chat_id: str | None = None) -> None:
        self.failing_chat_id = failing_chat_id
        self.messages: list[tuple[str, str]] = []

    async def send_message(self, *, chat_id: str, text: str) -> None:
        if chat_id == self.failing_chat_id:
            raise TelegramDeliveryError("TEST_FAILURE", retryable=True)
        self.messages.append((chat_id, text))


def snapshot(
    instrument_id: int,
    *,
    status: TechnicalStatus,
    analysis_date: date,
    revision: str,
) -> AnalysisSnapshot:
    return AnalysisSnapshot(
        instrument_id=instrument_id,
        analysis_date=analysis_date,
        technical_status=status,
        fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
        close_price=Decimal("651.15"),
        previous_close_price=Decimal("640.00"),
        setup_score=Decimal("82"),
        consolidation_timeframe="WEEKLY" if status != TechnicalStatus.NO_SETUP else None,
        resistance_price=Decimal("604.98") if status != TechnicalStatus.NO_SETUP else None,
        source="UPSTOX",
        source_fetched_at=NOW,
        algorithm_version="technical-v18",
        candle_revision=revision,
        generated_at=NOW,
    )


@pytest.mark.anyio
async def test_trading_day_digest_is_per_user_text_only_and_not_persisted(
    db_session: AsyncSession,
) -> None:
    setup_user = AppUser(
        username="morning-setup-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    empty_user = AppUser(
        username="morning-empty-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    setup_instrument = Instrument(
        company=Company(name="Ramkrishna Forgings Limited"),
        exchange="NSE",
        trading_symbol="RKFORGE",
    )
    no_setup_instrument = Instrument(
        company=Company(name="No Setup Limited"),
        exchange="NSE",
        trading_symbol="NOSETUP",
    )
    db_session.add_all(
        (setup_user, empty_user, setup_instrument, no_setup_instrument)
    )
    await db_session.flush()
    db_session.add_all(
        (
            TelegramConnection(
                user_id=setup_user.id,
                telegram_chat_id="101",
                connected_at=NOW,
                updated_at=NOW,
            ),
            TelegramConnection(
                user_id=empty_user.id,
                telegram_chat_id="202",
                connected_at=NOW,
                updated_at=NOW,
            ),
            UserWatchlistItem(
                user_id=setup_user.id,
                instrument_id=setup_instrument.id,
                baseline_session=date(2026, 7, 31),
                created_at=NOW,
                updated_at=NOW,
            ),
            UserWatchlistItem(
                user_id=empty_user.id,
                instrument_id=no_setup_instrument.id,
                baseline_session=date(2026, 7, 31),
                created_at=NOW,
                updated_at=NOW,
            ),
            snapshot(
                setup_instrument.id,
                status=TechnicalStatus.CONSOLIDATING,
                analysis_date=date(2026, 7, 30),
                revision="older",
            ),
            snapshot(
                setup_instrument.id,
                status=TechnicalStatus.BREAKOUT_HOLDING,
                analysis_date=date(2026, 7, 31),
                revision="latest",
            ),
            snapshot(
                no_setup_instrument.id,
                status=TechnicalStatus.NO_SETUP,
                analysis_date=date(2026, 7, 31),
                revision="no-setup",
            ),
        )
    )
    await db_session.flush()
    sender = RecordingSender()
    calendar = FakeCalendar(is_open=True)

    result = await send_morning_watchlist_digests(
        db_session,
        calendar,
        sender,
        occurred_at=NOW,
    )

    assert calendar.requested_dates == [date(2026, 8, 3)]
    assert result.connected_user_count == 2
    assert result.delivered_user_count == 2
    assert result.failed_user_count == 0
    assert {chat_id for chat_id, _ in sender.messages} == {"101", "202"}
    setup_message = next(text for chat_id, text in sender.messages if chat_id == "101")
    empty_message = next(text for chat_id, text in sender.messages if chat_id == "202")
    assert "Ramkrishna Forgings Limited (RKFORGE)" in setup_message
    assert "Breakout Holding - Weekly" in setup_message
    assert "Close: INR 651.15 (+1.74%)" in setup_message
    assert "Resistance: INR 604.98" in setup_message
    assert "No current breakout setups" in empty_message
    assert "NOSETUP" not in empty_message
    assert await db_session.scalar(
        select(func.count()).select_from(TelegramNotification)
    ) == 0


@pytest.mark.anyio
async def test_closed_market_sends_nothing(
    db_session: AsyncSession,
) -> None:
    sender = RecordingSender()
    result = await send_morning_watchlist_digests(
        db_session,
        FakeCalendar(is_open=False),
        sender,
        occurred_at=NOW,
    )

    assert result.is_trading_day is False
    assert result.message_count == 0
    assert sender.messages == []


@pytest.mark.anyio
async def test_delivery_failure_expires_without_an_outbox_row(
    db_session: AsyncSession,
) -> None:
    user = AppUser(
        username="morning-failure-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        TelegramConnection(
            user_id=user.id,
            telegram_chat_id="failed-chat",
            connected_at=NOW,
            updated_at=NOW,
        )
    )
    await db_session.flush()

    result = await send_morning_watchlist_digests(
        db_session,
        FakeCalendar(is_open=True),
        RecordingSender(failing_chat_id="failed-chat"),
        occurred_at=NOW,
    )

    assert result.failed_user_count == 1
    assert result.delivered_user_count == 0
    assert await db_session.scalar(
        select(func.count()).select_from(TelegramNotification)
    ) == 0


def test_large_watchlists_are_split_into_bounded_text_messages() -> None:
    setup = MorningSetup(
        company_name="Chunked Industries Limited",
        trading_symbol="CHUNK",
        status=TechnicalStatus.CONSOLIDATING,
        timeframe="DAILY",
        close_price=Decimal("100"),
        previous_close_price=Decimal("99"),
        resistance_price=Decimal("102"),
        setup_score=Decimal("75"),
        analysis_date=date(2026, 7, 31),
    )

    messages = build_morning_digest_messages(
        trading_date=date(2026, 8, 3),
        setups=[setup] * 5,
        content_limit=350,
    )

    assert len(messages) > 1
    assert all(len(message) <= 4096 for message in messages)
    assert "(1/" in messages[0]
