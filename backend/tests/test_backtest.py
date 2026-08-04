from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.domain.backtest import run_technical_backtest
from app.providers.contracts import DailyCandle


START = date(2025, 1, 1)


def candle(
    index: int,
    close: Decimal,
    *,
    open_price: Decimal | None = None,
    high: Decimal | None = None,
    low: Decimal | None = None,
) -> DailyCandle:
    session = START + timedelta(days=index)
    return DailyCandle(
        trading_date=session,
        timestamp=datetime.combine(session, datetime.min.time(), tzinfo=UTC),
        open=open_price if open_price is not None else close - Decimal("0.2"),
        high=high if high is not None else close + Decimal("2"),
        low=low if low is not None else close - Decimal("2"),
        close=close,
        volume=1000,
        open_interest=0,
    )


def breakout_history() -> tuple[DailyCandle, ...]:
    values: list[DailyCandle] = []
    for index in range(320):
        if index < 260:
            close = Decimal("100") + Decimal(index)
            values.append(candle(index, close))
        else:
            base_index = index - 260
            if base_index < 40:
                close = Decimal("360") + Decimal(base_index % 4)
                values.append(
                    candle(
                        index,
                        close,
                        high=close + Decimal("3"),
                        low=close - Decimal("3"),
                    )
                )
            elif base_index < 50:
                close = Decimal("360") + Decimal(base_index - 40) * Decimal("0.4")
                values.append(
                    candle(
                        index,
                        close,
                        high=close + Decimal("2.5"),
                        low=close - Decimal("2.5"),
                    )
                )
            else:
                close = Decimal("364") + Decimal(base_index - 50) * Decimal("0.4")
                values.append(
                    candle(
                        index,
                        close,
                        high=close + Decimal("0.5"),
                        low=close - Decimal("0.5"),
                    )
                )
    for index in (265, 280, 295):
        values[index] = candle(
            index,
            Decimal("365"),
            open_price=Decimal("366"),
            high=Decimal("370"),
            low=Decimal("363"),
        )
    for offset in range(1, 66):
        values.append(
            candle(
                319 + offset,
                Decimal("368") + Decimal(offset) * Decimal("0.2"),
                high=Decimal("368.5") + Decimal(offset) * Decimal("0.2"),
                low=Decimal("367.5") + Decimal(offset) * Decimal("0.2"),
            )
        )
    return tuple(values)


def benchmark_history(
    stock: tuple[DailyCandle, ...],
) -> tuple[DailyCandle, ...]:
    values: list[DailyCandle] = []
    for index, item in enumerate(stock):
        if index < 260:
            close = Decimal("100") + Decimal(index) * Decimal("0.10")
        else:
            close = Decimal("126") - Decimal(min(index, 319) - 260) * Decimal("0.07")
        values.append(
            DailyCandle(
                trading_date=item.trading_date,
                timestamp=item.timestamp,
                open=close,
                high=close + Decimal("0.1"),
                low=close - Decimal("0.1"),
                close=close,
                volume=1000,
                open_interest=0,
            )
        )
    return tuple(values)


def test_backtest_uses_historical_prefix_and_measures_forward_outcomes() -> None:
    history = breakout_history()
    report = run_technical_backtest(
        history,
        benchmark_candles=benchmark_history(history),
    )

    assert report.signal_count >= 1
    assert all(
        signal.forward_returns_percent[20] >= 0
        for signal in report.signals
    )
    assert Decimal("0") <= report.false_breakout_rate_percent <= Decimal("100")
    assert report.average_benchmark_relative_returns_percent is not None


def test_backtest_empty_result_is_explicit_not_zero_performance() -> None:
    history = tuple(
        candle(index, Decimal("100")) for index in range(320)
    )
    benchmark = tuple(
        candle(index, Decimal("100")) for index in range(320)
    )

    report = run_technical_backtest(
        history,
        benchmark_candles=benchmark,
    )

    assert report.signal_count == 0
    assert report.average_forward_returns_percent[20] is None
    assert report.false_breakout_rate_percent is None
