from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.providers.contracts import (
    AnalysisMarketDataProvider,
    ExchangeCalendarProvider,
)


NSE_TIMEZONE = ZoneInfo("Asia/Kolkata")
DEFAULT_ANALYSIS_CUTOFF = time(16, 0)
MAX_SESSION_LOOKBACK_DAYS = 14
PROVIDER_AVAILABILITY_LOOKBACK_DAYS = 14


class MarketSessionResolutionError(RuntimeError):
    pass


async def resolve_latest_completed_nse_session(
    provider: ExchangeCalendarProvider,
    *,
    now: datetime,
    ordinary_cutoff: time = DEFAULT_ANALYSIS_CUTOFF,
) -> date:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware.")

    local_now = now.astimezone(NSE_TIMEZONE)
    candidate = local_now.date()

    for _ in range(MAX_SESSION_LOOKBACK_DAYS):
        session = await provider.get_nse_session(candidate)
        if session.is_open:
            if candidate < local_now.date():
                return candidate

            if session.closes_at is not None:
                completed = local_now >= session.closes_at.astimezone(NSE_TIMEZONE)
            else:
                completed = local_now.time() >= ordinary_cutoff
            if completed:
                return candidate

        candidate -= timedelta(days=1)

    raise MarketSessionResolutionError(
        "No completed NSE session found in the configured lookback window."
    )


async def resolve_latest_available_nse_session(
    provider: AnalysisMarketDataProvider,
    *,
    benchmark_instrument_key: str,
    now: datetime,
) -> date:
    completed_session = await resolve_latest_completed_nse_session(
        provider,
        now=now,
    )
    candles = await provider.get_daily_candles(
        instrument_key=benchmark_instrument_key,
        from_date=(
            completed_session
            - timedelta(days=PROVIDER_AVAILABILITY_LOOKBACK_DAYS)
        ),
        to_date=completed_session,
    )
    available_dates = [
        candle.trading_date
        for candle in candles
        if candle.trading_date <= completed_session
    ]
    if completed_session not in available_dates:
        intraday_candles = await provider.get_intraday_daily_candles(
            instrument_key=benchmark_instrument_key,
        )
        if completed_session in {
            candle.trading_date for candle in intraday_candles
        }:
            return completed_session
    if not available_dates:
        raise MarketSessionResolutionError(
            "Upstox has no published benchmark candle in the availability window."
        )
    return max(available_dates)
