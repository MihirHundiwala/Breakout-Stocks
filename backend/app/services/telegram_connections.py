from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import re
import secrets

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    TelegramBotState,
    TelegramConnection,
    TelegramNotification,
)
from app.providers.telegram import (
    TelegramClient,
    TelegramDeliveryError,
    TelegramUpdate,
)
from app.services.distributed_rate_limit import postgres_advisory_lease


TELEGRAM_USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{5,32}$")
LINK_TTL = timedelta(minutes=15)
TELEGRAM_UPDATE_POLLER_LOCK_ID = 7_431_902_615


class InvalidTelegramUsernameError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TelegramConnectionView:
    connected: bool
    pending: bool
    username: str | None


@dataclass(frozen=True, slots=True)
class TelegramLinkResult:
    connection: TelegramConnectionView
    bot_url: str | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class TelegramUpdateResult:
    received_count: int
    connected_count: int


def normalize_telegram_username(value: str) -> str:
    normalized = value.strip().removeprefix("@").lower()
    if TELEGRAM_USERNAME_PATTERN.fullmatch(normalized) is None:
        raise InvalidTelegramUsernameError()
    return normalized


def normalize_bot_username(value: str) -> str:
    normalized = normalize_telegram_username(value)
    if not normalized.endswith("bot"):
        raise InvalidTelegramUsernameError()
    return normalized


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


async def get_telegram_connection(
    session: AsyncSession,
    *,
    user_id: int,
) -> TelegramConnectionView:
    connection = await session.get(TelegramConnection, user_id)
    if connection is None:
        return TelegramConnectionView(False, False, None)
    return TelegramConnectionView(
        connected=connection.telegram_chat_id is not None,
        pending=connection.link_token_digest is not None,
        username=connection.telegram_username,
    )


async def create_telegram_link(
    session: AsyncSession,
    *,
    user_id: int,
    bot_username: str,
    occurred_at: datetime | None = None,
) -> TelegramLinkResult:
    event_time = occurred_at or datetime.now(UTC)
    normalized_bot = normalize_bot_username(bot_username)
    raw_token = secrets.token_urlsafe(24)
    expires_at = event_time + LINK_TTL
    async with session.begin():
        connection = await session.scalar(
            select(TelegramConnection)
            .where(TelegramConnection.user_id == user_id)
            .with_for_update()
        )
        if connection is not None and connection.telegram_chat_id is not None:
            return TelegramLinkResult(
                TelegramConnectionView(
                    True,
                    False,
                    connection.telegram_username,
                ),
                None,
                None,
            )
        if connection is None:
            connection = TelegramConnection(
                user_id=user_id,
                link_token_digest=_digest(raw_token),
                link_expires_at=expires_at,
                updated_at=event_time,
            )
            session.add(connection)
        else:
            connection.link_token_digest = _digest(raw_token)
            connection.link_expires_at = expires_at
            connection.updated_at = event_time
        await session.flush()
    return TelegramLinkResult(
        TelegramConnectionView(False, True, None),
        f"https://t.me/{normalized_bot}?start={raw_token}",
        expires_at,
    )


async def disconnect_telegram(
    session: AsyncSession,
    *,
    user_id: int,
) -> bool:
    async with session.begin():
        connection = await session.get(
            TelegramConnection,
            user_id,
            with_for_update=True,
        )
        if connection is None:
            return False
        await session.execute(
            delete(TelegramNotification).where(
                TelegramNotification.user_id == user_id
            )
        )
        await session.delete(connection)
    return True


def _start_token(update: TelegramUpdate) -> str | None:
    message = update.message
    if message is None or message.chat.type != "private" or not message.text:
        return None
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].split("@", 1)[0] != "/start":
        return None
    return parts[1].strip() or None


async def _current_offset(session: AsyncSession) -> int:
    state = await session.get(TelegramBotState, 1)
    return state.next_update_id if state is not None else 0


async def _process_telegram_updates(
    session_factory: async_sessionmaker[AsyncSession],
    client: TelegramClient,
    *,
    occurred_at: datetime | None = None,
) -> TelegramUpdateResult:
    event_time = occurred_at or datetime.now(UTC)
    async with session_factory() as session:
        offset = await _current_offset(session)
    updates = await client.get_updates(offset=offset)
    if not updates:
        return TelegramUpdateResult(0, 0)

    replies: list[tuple[str, str]] = []
    connected_count = 0
    async with session_factory() as session:
        async with session.begin():
            state = await session.get(TelegramBotState, 1, with_for_update=True)
            if state is None:
                state = TelegramBotState(id=1, next_update_id=0, updated_at=event_time)
                session.add(state)
            for update in sorted(updates, key=lambda item: item.update_id):
                state.next_update_id = max(
                    state.next_update_id,
                    update.update_id + 1,
                )
                token = _start_token(update)
                message = update.message
                if token is None or message is None:
                    continue
                chat_id = str(message.chat.id)
                pending = await session.scalar(
                    select(TelegramConnection)
                    .where(
                        TelegramConnection.link_token_digest == _digest(token),
                        TelegramConnection.link_expires_at >= event_time,
                    )
                    .with_for_update()
                )
                if pending is None:
                    replies.append((chat_id, "This connection link is invalid or expired. Create a new link in Breakout Tracker."))
                    continue
                actual_username = (
                    message.sender.username.lower()
                    if message.sender is not None
                    and message.sender.username is not None
                    else None
                )
                existing = await session.scalar(
                    select(TelegramConnection).where(
                        TelegramConnection.telegram_chat_id == chat_id,
                        TelegramConnection.user_id != pending.user_id,
                    )
                )
                if existing is not None:
                    replies.append((chat_id, "This Telegram account is already connected to another Breakout Tracker login."))
                    continue
                pending.telegram_chat_id = chat_id
                pending.telegram_username = actual_username
                pending.link_token_digest = None
                pending.link_expires_at = None
                pending.connected_at = event_time
                pending.updated_at = event_time
                connected_count += 1
                replies.append((chat_id, "Telegram alerts are now connected to your Breakout Tracker watchlist."))
            state.updated_at = event_time

    for chat_id, text in replies:
        try:
            await client.send_alert(chat_id=chat_id, caption=text, photos=[])
        except TelegramDeliveryError:
            # Linking is authoritative; a confirmation-message failure is harmless.
            pass
    return TelegramUpdateResult(len(updates), connected_count)


async def process_telegram_updates(
    session_factory: async_sessionmaker[AsyncSession],
    client: TelegramClient,
    *,
    occurred_at: datetime | None = None,
) -> TelegramUpdateResult:
    async with postgres_advisory_lease(
        session_factory,
        lock_id=TELEGRAM_UPDATE_POLLER_LOCK_ID,
    ) as acquired:
        if not acquired:
            return TelegramUpdateResult(0, 0)
        return await _process_telegram_updates(
            session_factory,
            client,
            occurred_at=occurred_at,
        )
