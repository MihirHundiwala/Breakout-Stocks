import argparse
import asyncio
import json
from decimal import Decimal

from sqlalchemy import select

from app.db.session import async_session_factory, engine
from app.domain.backtest import run_technical_backtest
from app.models import DailyCandle, Instrument
from app.providers.contracts import DailyCandle as DomainCandle
from app.repositories.live_data import list_benchmark_daily_candles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest stored daily candles without provider calls."
    )
    parser.add_argument("--instrument-id", type=int, required=True)
    parser.add_argument(
        "--benchmark-code",
        default="NIFTY_500",
        help="Stored market benchmark code (default: NIFTY_500).",
    )
    return parser.parse_args()


async def load_candles(instrument_id: int) -> tuple[DomainCandle, ...]:
    async with async_session_factory() as session:
        exists = await session.scalar(
            select(Instrument.id).where(Instrument.id == instrument_id)
        )
        if exists is None:
            raise ValueError("INSTRUMENT_NOT_FOUND")
        rows = list(
            await session.scalars(
                select(DailyCandle)
                .where(DailyCandle.instrument_id == instrument_id)
                .order_by(DailyCandle.trading_date)
            )
        )
    return tuple(
        DomainCandle(
            trading_date=item.trading_date,
            timestamp=item.source_timestamp,
            open=item.open_price,
            high=item.high_price,
            low=item.low_price,
            close=item.close_price,
            volume=item.volume,
            open_interest=item.open_interest,
        )
        for item in rows
    )


async def load_benchmark_candles(
    benchmark_code: str,
) -> tuple[DomainCandle, ...]:
    async with async_session_factory() as session:
        rows = await list_benchmark_daily_candles(
            session,
            benchmark_code=benchmark_code.strip().upper(),
        )
    if not rows:
        raise ValueError("BENCHMARK_NOT_FOUND")
    return tuple(
        DomainCandle(
            trading_date=item.trading_date,
            timestamp=item.source_timestamp,
            open=item.open_price,
            high=item.high_price,
            low=item.low_price,
            close=item.close_price,
            volume=item.volume,
            open_interest=item.open_interest,
        )
        for item in rows
    )


def json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[union-attr]
    return value


async def main() -> int:
    args = parse_args()
    try:
        candles = await load_candles(args.instrument_id)
        benchmark = await load_benchmark_candles(args.benchmark_code)
        report = run_technical_backtest(candles, benchmark_candles=benchmark)
    except ValueError as error:
        print(f"BACKTEST_FAILED code={error}")
        return 1
    finally:
        await engine.dispose()

    payload = {
        "instrument_id": args.instrument_id,
        "benchmark_code": args.benchmark_code.strip().upper(),
        "signal_count": report.signal_count,
        "average_forward_returns_percent": report.average_forward_returns_percent,
        "average_benchmark_relative_returns_percent": report.average_benchmark_relative_returns_percent,
        "average_maximum_adverse_excursion_percent": report.average_maximum_adverse_excursion_percent,
        "false_breakout_rate_percent": report.false_breakout_rate_percent,
        "survivorship_bias_warning": "Stored/current instruments are not a point-in-time NSE universe.",
    }
    print(json.dumps(json_value(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
