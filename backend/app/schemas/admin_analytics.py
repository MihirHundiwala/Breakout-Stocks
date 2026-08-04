from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models import TechnicalStatus


class AdminUserAnalytics(BaseModel):
    registered_users: int
    new_users_7d: int
    new_users_30d: int
    active_users_7d: int
    active_users_30d: int
    telegram_connected_users: int


class AdminStockAnalytics(BaseModel):
    tracked_stocks: int
    active_watchlist_memberships: int
    average_stocks_per_registered_user: Decimal
    setup_distribution: dict[TechnicalStatus, int]


class AdminJobAnalytics(BaseModel):
    pending_jobs: int
    retry_scheduled_jobs: int
    running_jobs: int
    oldest_pending_job_created_at: datetime | None
    latest_analysis_date: date | None


class AdminAnalyticsResponse(BaseModel):
    generated_at: datetime
    users: AdminUserAnalytics
    stocks: AdminStockAnalytics
    jobs: AdminJobAnalytics
