import asyncio
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.providers.errors import ProviderError
from app.providers.upstox import UpstoxClient
from app.services.market_sessions import resolve_latest_completed_nse_session


async def main() -> int:
    settings = get_settings()
    if settings.upstox_access_token is None:
        print("LIVE_UPSTOX_FAILED code=MARKET_DATA_NOT_CONFIGURED")
        return 1

    try:
        async with UpstoxClient(
            access_token=settings.upstox_access_token,
            timeout_seconds=settings.upstox_timeout_seconds,
        ) as provider:
            candidates = await provider.search_nse_equities(
                query="RELIANCE",
                limit=10,
            )
            candidate = next(
                (item for item in candidates if item.trading_symbol == "RELIANCE"),
                None,
            )
            if candidate is None:
                print("LIVE_UPSTOX_FAILED code=SMOKE_INSTRUMENT_NOT_FOUND")
                return 1

            target = await resolve_latest_completed_nse_session(
                provider,
                now=datetime.now(UTC),
            )
            candles = await provider.get_daily_candles(
                instrument_key=candidate.instrument_key,
                from_date=target - timedelta(days=14),
                to_date=target,
            )
            intraday_daily = await provider.get_intraday_daily_candles(
                instrument_key=candidate.instrument_key,
            )
            fundamentals = await provider.get_fundamentals(isin=candidate.isin)
    except ProviderError as error:
        print(f"LIVE_UPSTOX_FAILED code={error.code}")
        return 1
    except Exception:
        print("LIVE_UPSTOX_FAILED code=LOCAL_SMOKE_ERROR")
        return 1

    print("LIVE_UPSTOX_OK")
    print(f"symbol={candidate.trading_symbol}")
    print(f"session={target.isoformat()}")
    print(f"candles={len(candles)}")
    print(
        "candle_range="
        + (
            f"{candles[0].trading_date.isoformat()}.."
            f"{candles[-1].trading_date.isoformat()}"
            if candles
            else "EMPTY"
        )
    )
    print(
        "intraday_daily_latest="
        + (
            intraday_daily[-1].trading_date.isoformat()
            if intraday_daily
            else "EMPTY"
        )
    )
    print(f"fundamental_groups={len(fundamentals.available_groups)}")
    print(f"fundamental_periods={len(fundamentals.periods)}")
    print(
        "sector="
        + (fundamentals.profile.sector if fundamentals.profile is not None else "UNKNOWN")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
