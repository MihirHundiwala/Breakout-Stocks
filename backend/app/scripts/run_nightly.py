import asyncio
from datetime import UTC, datetime

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.providers.errors import ProviderError
from app.providers.upstox import UpstoxClient
from app.services.nightly_scan import schedule_latest_available_session
from app.services.distributed_rate_limit import PostgresRequestRateLimiter

async def main() -> int:
    settings = get_settings()
    if settings.upstox_access_token is None:
        print("NIGHTLY_FAILED code=MARKET_DATA_NOT_CONFIGURED")
        return 1

    now = datetime.now(UTC)
    try:
        async with UpstoxClient(
            access_token=settings.upstox_access_token,
            timeout_seconds=settings.upstox_timeout_seconds,
            requests_per_second=settings.worker_upstox_requests_per_second,
            request_rate_limiter=PostgresRequestRateLimiter(
                async_session_factory
            ),
        ) as provider:
            async with async_session_factory() as session:
                result = await schedule_latest_available_session(
                    session,
                    provider,
                    benchmark_instrument_key=settings.nifty_500_instrument_key,
                    occurred_at=now,
                )
    except ProviderError as error:
        print(f"NIGHTLY_FAILED code={error.code}")
        return 1
    except Exception:
        print("NIGHTLY_FAILED code=NIGHTLY_RUNTIME_ERROR")
        return 1
    finally:
        await engine.dispose()

    print(
        "NIGHTLY_QUEUED "
        f"session={result.target_session.isoformat()} "
        f"enqueued={result.enqueued_count} "
        f"retargeted={result.retargeted_count} "
        f"active={result.skipped_active_count} "
        f"completed={result.skipped_completed_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
