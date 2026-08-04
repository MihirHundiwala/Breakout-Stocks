from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BenchmarkDailyCandle, MarketBenchmark
from app.providers.contracts import DailyCandle
from app.repositories.live_data import (
    ensure_market_benchmark,
    list_benchmark_daily_candles,
    upsert_benchmark_daily_candles,
)


FETCHED_AT = datetime(2026, 7, 25, 11, 0, tzinfo=UTC)


def provider_candle(*, close: Decimal = Decimal("25000")) -> DailyCandle:
    return DailyCandle(
        trading_date=date(2026, 7, 24),
        timestamp=FETCHED_AT,
        open=close - Decimal("50"),
        high=close + Decimal("100"),
        low=close - Decimal("100"),
        close=close,
        volume=1000,
        open_interest=0,
    )


async def persisted_benchmark(db_session: AsyncSession) -> MarketBenchmark:
    return await ensure_market_benchmark(
        db_session,
        code="NIFTY_500",
        name="Nifty 500",
        provider="UPSTOX",
        instrument_key="NSE_INDEX|Nifty 500",
        source_fetched_at=FETCHED_AT,
    )


@pytest.mark.anyio
async def test_benchmark_identity_and_candle_upserts_are_idempotent(
    db_session: AsyncSession,
) -> None:
    first = await persisted_benchmark(db_session)
    second = await persisted_benchmark(db_session)
    await upsert_benchmark_daily_candles(
        db_session,
        benchmark_id=first.id,
        candles=(provider_candle(),),
        fetched_at=FETCHED_AT,
    )
    await upsert_benchmark_daily_candles(
        db_session,
        benchmark_id=first.id,
        candles=(provider_candle(close=Decimal("25100")),),
        fetched_at=FETCHED_AT,
    )

    rows = await list_benchmark_daily_candles(
        db_session,
        benchmark_code="NIFTY_500",
    )
    benchmark_count = await db_session.scalar(
        select(func.count()).select_from(MarketBenchmark)
    )

    assert first.id == second.id
    assert benchmark_count == 1
    assert len(rows) == 1
    assert rows[0].close_price == Decimal("25100")


@pytest.mark.anyio
async def test_benchmark_candle_rejects_invalid_ohlc(
    db_session: AsyncSession,
) -> None:
    benchmark = await persisted_benchmark(db_session)
    db_session.add(
        BenchmarkDailyCandle(
            benchmark_id=benchmark.id,
            trading_date=date(2026, 7, 24),
            open_price=Decimal("25000"),
            high_price=Decimal("25010"),
            low_price=Decimal("24900"),
            close_price=Decimal("25100"),
            volume=1000,
            open_interest=0,
            source="UPSTOX",
            source_timestamp=FETCHED_AT,
            fetched_at=FETCHED_AT,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()
