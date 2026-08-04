import asyncio
from datetime import UTC, datetime

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.providers.errors import ProviderError
from app.providers.telegram import TelegramClient
from app.providers.upstox import UpstoxClient
from app.services.morning_digest import send_morning_watchlist_digests
from app.services.distributed_rate_limit import PostgresRequestRateLimiter


async def main() -> int:
    settings = get_settings()
    if not settings.telegram_notifications_enabled:
        print("MORNING_DIGEST_SKIPPED code=TELEGRAM_DISABLED")
        return 0
    if settings.upstox_access_token is None:
        print("MORNING_DIGEST_FAILED code=MARKET_DATA_NOT_CONFIGURED")
        return 1

    try:
        request_rate_limiter = PostgresRequestRateLimiter(
            async_session_factory
        )
        async with (
            UpstoxClient(
                access_token=settings.upstox_access_token,
                timeout_seconds=settings.upstox_timeout_seconds,
                requests_per_second=settings.worker_upstox_requests_per_second,
                request_rate_limiter=request_rate_limiter,
            ) as calendar_provider,
            TelegramClient(
                bot_token=settings.telegram_bot_token.get_secret_value(),
                timeout_seconds=settings.telegram_timeout_seconds,
                minimum_interval_seconds=(
                    1 / settings.telegram_requests_per_second
                ),
                request_rate_limiter=request_rate_limiter,
            ) as sender,
            async_session_factory() as session,
        ):
            result = await send_morning_watchlist_digests(
                session,
                calendar_provider,
                sender,
                occurred_at=datetime.now(UTC),
            )
    except ProviderError as error:
        print(f"MORNING_DIGEST_FAILED code={error.code}")
        return 1
    except Exception as error:
        print(
            "MORNING_DIGEST_FAILED code=MORNING_DIGEST_RUNTIME_ERROR "
            f"error_type={type(error).__name__}"
        )
        return 1
    finally:
        await engine.dispose()

    if not result.is_trading_day:
        print("MORNING_DIGEST_SKIPPED code=NSE_CLOSED")
        return 0
    print(
        "MORNING_DIGEST_SENT "
        f"connected_users={result.connected_user_count} "
        f"delivered_users={result.delivered_user_count} "
        f"failed_users={result.failed_user_count} "
        f"messages={result.message_count}"
    )
    return 0 if result.failed_user_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
