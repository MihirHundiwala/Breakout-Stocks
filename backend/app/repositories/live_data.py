from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BenchmarkDailyCandle,
    DailyCandle,
    MarketBenchmark,
    ProviderInstrumentIdentity,
)
from app.providers.contracts import DailyCandle as ProviderCandle


async def get_active_provider_identity(
    session: AsyncSession,
    instrument_id: int,
    provider: str,
) -> ProviderInstrumentIdentity | None:
    return await session.scalar(
        select(ProviderInstrumentIdentity).where(
            ProviderInstrumentIdentity.instrument_id == instrument_id,
            ProviderInstrumentIdentity.provider == provider,
            ProviderInstrumentIdentity.effective_to.is_(None),
        )
    )


async def upsert_daily_candles(
    session: AsyncSession,
    *,
    instrument_id: int,
    candles: tuple[ProviderCandle, ...],
    fetched_at: datetime,
    source: str = "UPSTOX",
) -> None:
    if not candles:
        return
    rows = [
        {
            "instrument_id": instrument_id,
            "trading_date": candle.trading_date,
            "open_price": candle.open,
            "high_price": candle.high,
            "low_price": candle.low,
            "close_price": candle.close,
            "volume": candle.volume,
            "open_interest": candle.open_interest,
            "source": source,
            "source_timestamp": candle.timestamp,
            "fetched_at": fetched_at,
        }
        for candle in candles
    ]
    statement = insert(DailyCandle).values(rows)
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_daily_candles_instrument_date",
            set_={
                "open_price": statement.excluded.open_price,
                "high_price": statement.excluded.high_price,
                "low_price": statement.excluded.low_price,
                "close_price": statement.excluded.close_price,
                "volume": statement.excluded.volume,
                "open_interest": statement.excluded.open_interest,
                "source": statement.excluded.source,
                "source_timestamp": statement.excluded.source_timestamp,
                "fetched_at": statement.excluded.fetched_at,
            },
        )
    )


async def list_daily_candles(
    session: AsyncSession,
    *,
    instrument_id: int,
    from_date: date,
    to_date: date,
) -> list[DailyCandle]:
    return list(
        await session.scalars(
            select(DailyCandle)
            .where(
                DailyCandle.instrument_id == instrument_id,
                DailyCandle.trading_date >= from_date,
                DailyCandle.trading_date <= to_date,
            )
            .order_by(DailyCandle.trading_date)
        )
    )


async def ensure_market_benchmark(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    provider: str,
    instrument_key: str,
    source_fetched_at: datetime,
) -> MarketBenchmark:
    statement = insert(MarketBenchmark).values(
        code=code,
        name=name,
        provider=provider,
        instrument_key=instrument_key,
        source_fetched_at=source_fetched_at,
    )
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_market_benchmarks_code",
            set_={
                "name": statement.excluded.name,
                "provider": statement.excluded.provider,
                "instrument_key": statement.excluded.instrument_key,
                "source_fetched_at": statement.excluded.source_fetched_at,
            },
        )
    )
    benchmark = await session.scalar(
        select(MarketBenchmark).where(MarketBenchmark.code == code)
    )
    if benchmark is None:
        raise RuntimeError("Market benchmark upsert did not return an identity.")
    return benchmark


async def upsert_benchmark_daily_candles(
    session: AsyncSession,
    *,
    benchmark_id: int,
    candles: tuple[ProviderCandle, ...],
    fetched_at: datetime,
    source: str = "UPSTOX",
) -> None:
    if not candles:
        return
    rows = [
        {
            "benchmark_id": benchmark_id,
            "trading_date": candle.trading_date,
            "open_price": candle.open,
            "high_price": candle.high,
            "low_price": candle.low,
            "close_price": candle.close,
            "volume": candle.volume,
            "open_interest": candle.open_interest,
            "source": source,
            "source_timestamp": candle.timestamp,
            "fetched_at": fetched_at,
        }
        for candle in candles
    ]
    statement = insert(BenchmarkDailyCandle).values(rows)
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_benchmark_daily_candles_benchmark_date",
            set_={
                "open_price": statement.excluded.open_price,
                "high_price": statement.excluded.high_price,
                "low_price": statement.excluded.low_price,
                "close_price": statement.excluded.close_price,
                "volume": statement.excluded.volume,
                "open_interest": statement.excluded.open_interest,
                "source": statement.excluded.source,
                "source_timestamp": statement.excluded.source_timestamp,
                "fetched_at": statement.excluded.fetched_at,
            },
        )
    )


async def list_benchmark_daily_candles(
    session: AsyncSession,
    *,
    benchmark_code: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[BenchmarkDailyCandle]:
    query = (
        select(BenchmarkDailyCandle)
        .join(MarketBenchmark)
        .where(MarketBenchmark.code == benchmark_code)
    )
    if from_date is not None:
        query = query.where(
            BenchmarkDailyCandle.trading_date >= from_date
        )
    if to_date is not None:
        query = query.where(BenchmarkDailyCandle.trading_date <= to_date)
    return list(
        await session.scalars(
            query.order_by(BenchmarkDailyCandle.trading_date)
        )
    )
