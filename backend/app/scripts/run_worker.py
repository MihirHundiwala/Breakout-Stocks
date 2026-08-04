import argparse
import asyncio
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from time import monotonic

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.models import AnalysisJob, AnalysisJobStatus, AnalysisJobType
from app.providers.errors import ProviderError
from app.providers.upstox import UpstoxClient
from app.providers.telegram import TelegramClient, TelegramDeliveryError
from app.services.fundamental_refresh import FundamentalRefreshHandler
from app.services.distributed_rate_limit import PostgresRequestRateLimiter
from app.services.live_onboarding import LiveOnboardingHandler
from app.services.onboarding_worker import (
    ClaimedOnboardingJob,
    WorkerRunOutcome,
    process_one_onboarding_job,
    recover_stale_onboarding_jobs,
)
from app.services.nightly_scan import (
    NightlyScheduleResult,
    schedule_active_watchlist,
    schedule_worker_startup,
)
from app.services.telegram_connections import process_telegram_updates
from app.services.telegram_delivery import (
    TelegramDeliveryOutcome,
    active_telegram_notification_count,
    process_one_telegram_notification,
    recover_stale_telegram_notifications,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process durable analysis jobs.")
    parser.add_argument(
        "--drain",
        action="store_true",
        help="Exit when there is no currently eligible job.",
    )
    parser.add_argument(
        "--until-settled",
        action="store_true",
        help="Wait through retry delays until no pending/running jobs remain.",
    )
    return parser.parse_args()


async def active_job_count() -> int:
    async with async_session_factory() as session:
        value = await session.scalar(
            select(func.count())
            .select_from(AnalysisJob)
            .where(
                AnalysisJob.status.in_(
                    (AnalysisJobStatus.PENDING, AnalysisJobStatus.RUNNING)
                )
            )
        )
    return int(value or 0)


def print_startup_schedule(result: NightlyScheduleResult) -> None:
    print(
        "WORKER_STARTUP_SCHEDULE "
        f"session={result.target_session.isoformat()} "
        f"enqueued={result.enqueued_count} "
        f"retargeted={result.retargeted_count} "
        f"active={result.skipped_active_count} "
        f"completed={result.skipped_completed_count}"
    )


async def main() -> int:
    args = parse_args()
    settings = get_settings()
    if settings.upstox_access_token is None:
        print("WORKER_DISABLED code=MARKET_DATA_NOT_CONFIGURED")
        return 0

    try:
        async with AsyncExitStack() as stack:
            request_rate_limiter = PostgresRequestRateLimiter(
                async_session_factory
            )
            provider = await stack.enter_async_context(
                UpstoxClient(
                    access_token=settings.upstox_access_token,
                    timeout_seconds=settings.upstox_timeout_seconds,
                    requests_per_second=settings.worker_upstox_requests_per_second,
                    request_rate_limiter=request_rate_limiter,
                )
            )
            telegram_client = None
            if settings.telegram_notifications_enabled:
                telegram_client = await stack.enter_async_context(
                    TelegramClient(
                        bot_token=settings.telegram_bot_token.get_secret_value(),
                        timeout_seconds=settings.telegram_timeout_seconds,
                        minimum_interval_seconds=(
                            1 / settings.telegram_requests_per_second
                        ),
                        request_rate_limiter=request_rate_limiter,
                    )
                )
            technical_handler = LiveOnboardingHandler(
                session_factory=async_session_factory,
                provider=provider,
                benchmark_instrument_key=settings.nifty_500_instrument_key,
                telegram_notifications_enabled=(
                    settings.telegram_notifications_enabled
                ),
            )
            fundamental_handler = FundamentalRefreshHandler(
                session_factory=async_session_factory,
                provider=provider,
            )

            async def handler(job: ClaimedOnboardingJob) -> None:
                if job.job_type == AnalysisJobType.REFRESH_FUNDAMENTALS:
                    await fundamental_handler(job)
                else:
                    await technical_handler(job)

            now = datetime.now(UTC)
            async with async_session_factory() as session:
                recovery = await recover_stale_onboarding_jobs(
                    session,
                    stale_before=now
                    - timedelta(seconds=settings.worker_stale_after_seconds),
                    occurred_at=now,
                    maximum_attempts=settings.worker_maximum_attempts,
                    retry_delay_seconds=settings.worker_retry_base_seconds,
                )
            print(
                "WORKER_RECOVERY "
                f"requeued={recovery.requeued_count} "
                f"failed={recovery.failed_count} "
                f"cancelled={recovery.cancelled_count}"
            )
            if telegram_client is not None:
                async with async_session_factory() as session:
                    recovered_notifications = (
                        await recover_stale_telegram_notifications(
                            session,
                            stale_before=now
                            - timedelta(
                                seconds=settings.worker_stale_after_seconds
                            ),
                            occurred_at=now,
                        )
                    )
                print(
                    "TELEGRAM_RECOVERY "
                    f"requeued={recovered_notifications}"
                )

            startup_time = datetime.now(UTC)
            async with async_session_factory() as session:
                startup_schedule = await schedule_worker_startup(
                    session,
                    provider,
                    enabled=settings.worker_schedule_on_startup,
                    benchmark_instrument_key=settings.nifty_500_instrument_key,
                    occurred_at=startup_time,
                )
            if startup_schedule is None:
                print("WORKER_STARTUP_SCHEDULE disabled=true")
                startup_target_session = None
                startup_reconciliation_pending = False
            else:
                print_startup_schedule(startup_schedule)
                startup_target_session = startup_schedule.target_session
                startup_reconciliation_pending = (
                    startup_schedule.skipped_active_count > 0
                )

            next_telegram_poll_at = 0.0
            while True:
                if (
                    telegram_client is not None
                    and monotonic() >= next_telegram_poll_at
                ):
                    try:
                        update_result = await process_telegram_updates(
                            async_session_factory,
                            telegram_client,
                        )
                        if update_result.received_count:
                            print(
                                "TELEGRAM_UPDATES "
                                f"received={update_result.received_count} "
                                f"connected={update_result.connected_count}"
                            )
                    except TelegramDeliveryError as error:
                        print(f"TELEGRAM_UPDATES_FAILED code={error.code}")
                    next_telegram_poll_at = monotonic() + 5.0
                result = await process_one_onboarding_job(
                    async_session_factory,
                    handler,
                    maximum_attempts=settings.worker_maximum_attempts,
                    retry_base_seconds=settings.worker_retry_base_seconds,
                )
                if result.outcome != WorkerRunOutcome.NO_JOB:
                    print(f"WORKER_JOB id={result.job_id} outcome={result.outcome}")
                    if telegram_client is not None:
                        delivery = await process_one_telegram_notification(
                            async_session_factory,
                            telegram_client,
                            maximum_attempts=settings.worker_maximum_attempts,
                            retry_base_seconds=settings.worker_retry_base_seconds,
                        )
                        if delivery.outcome != TelegramDeliveryOutcome.NO_NOTIFICATION:
                            print(
                                "TELEGRAM_NOTIFICATION "
                                f"id={delivery.notification_id} "
                                f"outcome={delivery.outcome}"
                            )
                    continue

                if telegram_client is not None:
                    delivery = await process_one_telegram_notification(
                        async_session_factory,
                        telegram_client,
                        maximum_attempts=settings.worker_maximum_attempts,
                        retry_base_seconds=settings.worker_retry_base_seconds,
                    )
                    if delivery.outcome != TelegramDeliveryOutcome.NO_NOTIFICATION:
                        print(
                            "TELEGRAM_NOTIFICATION "
                            f"id={delivery.notification_id} "
                            f"outcome={delivery.outcome}"
                        )
                        continue

                remaining_active_jobs = await active_job_count()
                remaining_notifications = 0
                if telegram_client is not None:
                    async with async_session_factory() as session:
                        remaining_notifications = (
                            await active_telegram_notification_count(session)
                        )
                if (
                    startup_reconciliation_pending
                    and startup_target_session is not None
                    and remaining_active_jobs == 0
                ):
                    async with async_session_factory() as session:
                        startup_schedule = await schedule_active_watchlist(
                            session,
                            target_session=startup_target_session,
                            occurred_at=datetime.now(UTC),
                        )
                    print_startup_schedule(startup_schedule)
                    startup_reconciliation_pending = (
                        startup_schedule.skipped_active_count > 0
                    )
                    if (
                        startup_schedule.enqueued_count > 0
                        or startup_schedule.retargeted_count > 0
                    ):
                        continue

                if args.until_settled:
                    if (
                        remaining_active_jobs == 0
                        and remaining_notifications == 0
                    ):
                        break
                elif args.drain:
                    break
                await asyncio.sleep(settings.worker_poll_seconds)
    except ProviderError as error:
        print(f"WORKER_FAILED code={error.code}")
        return 1
    except Exception as error:
        print(
            "WORKER_FAILED code=WORKER_RUNTIME_ERROR "
            f"error_type={type(error).__name__}"
        )
        return 1
    finally:
        await engine.dispose()

    print("WORKER_IDLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
