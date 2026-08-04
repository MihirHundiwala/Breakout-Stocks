from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AppUser, TelegramConnection, UserRole
from app.providers.telegram import TelegramChat, TelegramMessage, TelegramUpdate, TelegramUser
from app.services.telegram_connections import create_telegram_link, process_telegram_updates


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


class FakeTelegramClient:
    def __init__(self, updates: list[TelegramUpdate]) -> None:
        self.updates = updates
        self.offsets: list[int] = []
        self.messages: list[tuple[str, str]] = []

    async def get_updates(self, *, offset: int) -> list[TelegramUpdate]:
        self.offsets.append(offset)
        return self.updates

    async def send_alert(self, *, chat_id: str, caption: str, photos: list[object]) -> None:
        assert photos == []
        self.messages.append((chat_id, caption))


async def persist_user(session: AsyncSession, username: str) -> AppUser:
    user = AppUser(
        username=username,
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    session.add(user)
    await session.commit()
    return user


@pytest.mark.anyio
async def test_one_time_link_connects_verified_telegram_chat(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "telegram-user")
    result = await create_telegram_link(
        db_session,
        user_id=user.id,
        bot_username="breakout_tracker_bot",
        occurred_at=NOW,
    )
    assert result.bot_url is not None
    token = parse_qs(urlparse(result.bot_url).query)["start"][0]
    stored = await db_session.get(TelegramConnection, user.id)
    assert stored is not None
    assert stored.link_token_digest != token

    fake = FakeTelegramClient([
        TelegramUpdate(
            update_id=41,
            message=TelegramMessage(
                text=f"/start {token}",
                chat=TelegramChat(id=987654321, type="private"),
                sender=TelegramUser(id=987654321, username="MarketWatcher"),
            ),
        )
    ])
    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    update_result = await process_telegram_updates(
        factory,
        fake,  # type: ignore[arg-type]
        occurred_at=NOW,
    )

    await db_session.refresh(stored)
    assert update_result.connected_count == 1
    assert stored.telegram_chat_id == "987654321"
    assert stored.telegram_username == "marketwatcher"
    assert stored.link_token_digest is None
    assert fake.messages == [
        (
            "987654321",
            "Telegram alerts are now connected to your Breakout Tracker watchlist.",
        )
    ]


@pytest.mark.anyio
async def test_invalid_start_token_does_not_connect_user(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "pending-user")
    await create_telegram_link(
        db_session,
        user_id=user.id,
        bot_username="breakout_tracker_bot",
        occurred_at=NOW,
    )
    fake = FakeTelegramClient([
        TelegramUpdate(
            update_id=1,
            message=TelegramMessage(
                text="/start not-the-token",
                chat=TelegramChat(id=12, type="private"),
                sender=TelegramUser(id=12, username="someone"),
            ),
        )
    ])
    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    result = await process_telegram_updates(
        factory,
        fake,  # type: ignore[arg-type]
        occurred_at=NOW,
    )
    connection = await db_session.scalar(select(TelegramConnection))
    assert result.connected_count == 0
    assert connection is not None
    assert connection.telegram_chat_id is None
