from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisSnapshot,
    AppUser,
    TechnicalStatus,
    TelegramConnection,
    TrackedInstrument,
    UserRole,
    UserWatchlistItem,
)
from app.schemas.admin_analytics import (
    AdminAnalyticsResponse,
    AdminJobAnalytics,
    AdminStockAnalytics,
    AdminUserAnalytics,
)


async def get_admin_analytics(
    session: AsyncSession,
    *,
    occurred_at: datetime | None = None,
) -> AdminAnalyticsResponse:
    now = (occurred_at or datetime.now(UTC)).astimezone(UTC)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    user_counts = (
        await session.execute(
            select(
                func.count(AppUser.id).filter(
                    AppUser.role == UserRole.USER
                ),
                func.count(AppUser.id).filter(
                    AppUser.role == UserRole.USER,
                    AppUser.created_at >= seven_days_ago,
                ),
                func.count(AppUser.id).filter(
                    AppUser.role == UserRole.USER,
                    AppUser.created_at >= thirty_days_ago,
                ),
                func.count(AppUser.id).filter(
                    AppUser.role == UserRole.USER,
                    AppUser.is_active.is_(True),
                    AppUser.last_active_at >= seven_days_ago,
                ),
                func.count(AppUser.id).filter(
                    AppUser.role == UserRole.USER,
                    AppUser.is_active.is_(True),
                    AppUser.last_active_at >= thirty_days_ago,
                ),
            )
        )
    ).one()
    telegram_connected = await session.scalar(
        select(func.count(TelegramConnection.user_id))
        .join(AppUser, AppUser.id == TelegramConnection.user_id)
        .where(
            AppUser.role == UserRole.USER,
            AppUser.is_active.is_(True),
            TelegramConnection.telegram_chat_id.is_not(None),
        )
    )
    tracked_stocks = await session.scalar(
        select(func.count(TrackedInstrument.id)).where(
            TrackedInstrument.is_active.is_(True)
        )
    )
    memberships = await session.scalar(
        select(func.count(UserWatchlistItem.id)).where(
            UserWatchlistItem.is_active.is_(True)
        )
    )

    ranked = (
        select(
            AnalysisSnapshot.id.label("snapshot_id"),
            AnalysisSnapshot.instrument_id.label("instrument_id"),
            func.row_number().over(
                partition_by=AnalysisSnapshot.instrument_id,
                order_by=(
                    desc(AnalysisSnapshot.analysis_date),
                    desc(AnalysisSnapshot.generated_at),
                    desc(AnalysisSnapshot.id),
                ),
            ).label("snapshot_rank"),
        )
        .subquery()
    )
    status_rows = (
        await session.execute(
            select(AnalysisSnapshot.technical_status, func.count())
            .join(ranked, ranked.c.snapshot_id == AnalysisSnapshot.id)
            .join(
                TrackedInstrument,
                TrackedInstrument.instrument_id
                == AnalysisSnapshot.instrument_id,
            )
            .where(
                ranked.c.snapshot_rank == 1,
                TrackedInstrument.is_active.is_(True),
            )
            .group_by(AnalysisSnapshot.technical_status)
        )
    ).all()
    setup_distribution = {status: 0 for status in TechnicalStatus}
    setup_distribution.update({status: count for status, count in status_rows})

    job_counts = (
        await session.execute(
            select(
                func.count(AnalysisJob.id).filter(
                    AnalysisJob.status == AnalysisJobStatus.PENDING,
                    AnalysisJob.next_attempt_at <= now,
                ),
                func.count(AnalysisJob.id).filter(
                    AnalysisJob.status == AnalysisJobStatus.PENDING,
                    AnalysisJob.next_attempt_at > now,
                ),
                func.count(AnalysisJob.id).filter(
                    AnalysisJob.status == AnalysisJobStatus.RUNNING,
                ),
                func.min(AnalysisJob.created_at).filter(
                    AnalysisJob.status == AnalysisJobStatus.PENDING,
                ),
            )
        )
    ).one()
    latest_analysis_date = await session.scalar(
        select(func.max(AnalysisSnapshot.analysis_date))
    )
    registered_users = int(user_counts[0] or 0)
    active_memberships = int(memberships or 0)
    average = (
        Decimal(active_memberships) / Decimal(registered_users)
        if registered_users
        else Decimal("0")
    )
    return AdminAnalyticsResponse(
        generated_at=now,
        users=AdminUserAnalytics(
            registered_users=registered_users,
            new_users_7d=int(user_counts[1] or 0),
            new_users_30d=int(user_counts[2] or 0),
            active_users_7d=int(user_counts[3] or 0),
            active_users_30d=int(user_counts[4] or 0),
            telegram_connected_users=int(telegram_connected or 0),
        ),
        stocks=AdminStockAnalytics(
            tracked_stocks=int(tracked_stocks or 0),
            active_watchlist_memberships=active_memberships,
            average_stocks_per_registered_user=average.quantize(
                Decimal("0.01")
            ),
            setup_distribution=setup_distribution,
        ),
        jobs=AdminJobAnalytics(
            pending_jobs=int(job_counts[0] or 0),
            retry_scheduled_jobs=int(job_counts[1] or 0),
            running_jobs=int(job_counts[2] or 0),
            oldest_pending_job_created_at=job_counts[3],
            latest_analysis_date=latest_analysis_date,
        ),
    )
