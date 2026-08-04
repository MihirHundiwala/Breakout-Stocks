from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.technical_analysis import (
    TechnicalAnalysisConfig,
    analyze_technical_setup,
)
from app.models import TechnicalStatus
from app.providers.contracts import DailyCandle


DEFAULT_FORWARD_SESSIONS = (5, 20, 60)


@dataclass(frozen=True, slots=True)
class BacktestSignal:
    signal_date: date
    forward_returns_percent: dict[int, Decimal]
    benchmark_relative_returns_percent: dict[int, Decimal] | None
    maximum_adverse_excursion_percent: Decimal
    false_breakout: bool


@dataclass(frozen=True, slots=True)
class BacktestReport:
    signal_count: int
    average_forward_returns_percent: dict[int, Decimal | None]
    average_benchmark_relative_returns_percent: dict[int, Decimal | None] | None
    average_maximum_adverse_excursion_percent: Decimal | None
    false_breakout_rate_percent: Decimal | None
    signals: tuple[BacktestSignal, ...]


def _percent_change(current: Decimal, reference: Decimal) -> Decimal:
    return ((current - reference) / reference) * Decimal("100")


def _average(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def run_technical_backtest(
    candles: tuple[DailyCandle, ...],
    *,
    benchmark_candles: tuple[DailyCandle, ...],
    config: TechnicalAnalysisConfig = TechnicalAnalysisConfig(),
    forward_sessions: tuple[int, ...] = DEFAULT_FORWARD_SESSIONS,
    minimum_signal_spacing: int = 20,
) -> BacktestReport:
    if not forward_sessions or any(item < 1 for item in forward_sessions):
        raise ValueError("Forward session horizons must be positive.")
    if minimum_signal_spacing < 0:
        raise ValueError("minimum_signal_spacing cannot be negative.")

    ordered = tuple(sorted(candles, key=lambda item: item.trading_date))
    dates = [item.trading_date for item in ordered]
    if len(dates) != len(set(dates)):
        raise ValueError("Backtest candles contain duplicate sessions.")
    maximum_horizon = max(forward_sessions)
    required_history = max(
        config.minimum_sessions,
        config.long_sma_sessions + config.slope_lookback_sessions,
        config.high_lookback_sessions,
        config.base_sessions + 1,
    )
    benchmark_by_date = {
        item.trading_date: item for item in benchmark_candles
    }

    signals: list[BacktestSignal] = []
    last_signal_index: int | None = None
    for index in range(required_history - 1, len(ordered) - maximum_horizon):
        if (
            last_signal_index is not None
            and index - last_signal_index <= minimum_signal_spacing
        ):
            continue
        history = ordered[: index + 1]
        result = analyze_technical_setup(
            history,
            benchmark_candles=benchmark_candles,
            target_session=history[-1].trading_date,
            expected_sessions=[item.trading_date for item in history],
            config=config,
        )
        ready_consolidation = (
            result.status == TechnicalStatus.CONSOLIDATING
            and result.distance_to_resistance_pct is not None
            and Decimal("0")
            <= result.distance_to_resistance_pct
            <= config.maximum_consolidating_distance
            and result.base_depth_pct is not None
            and result.base_depth_pct >= config.minimum_base_depth
            and result.base_position is not None
            and result.base_position >= config.minimum_base_position
        )
        if result.status not in {
            TechnicalStatus.BREAKOUT,
            TechnicalStatus.EARLY_RECOVERY_BREAKOUT,
        } and not ready_consolidation:
            continue

        entry = history[-1].close
        returns = {
            horizon: _percent_change(ordered[index + horizon].close, entry)
            for horizon in forward_sessions
        }
        relative_returns = None
        benchmark_entry = benchmark_by_date.get(result.analysis_date)
        benchmark_outcomes = {
            horizon: benchmark_by_date.get(ordered[index + horizon].trading_date)
            for horizon in forward_sessions
        }
        if benchmark_entry is not None and all(benchmark_outcomes.values()):
            relative_returns = {
                horizon: returns[horizon]
                - _percent_change(
                    benchmark_outcomes[horizon].close,  # type: ignore[union-attr]
                    benchmark_entry.close,
                )
                for horizon in forward_sessions
            }
        future_window = ordered[index + 1 : index + maximum_horizon + 1]
        adverse = _percent_change(min(item.low for item in future_window), entry)
        false_horizon = 20 if 20 in returns else maximum_horizon
        signals.append(
            BacktestSignal(
                signal_date=result.analysis_date,
                forward_returns_percent=returns,
                benchmark_relative_returns_percent=relative_returns,
                maximum_adverse_excursion_percent=adverse,
                false_breakout=returns[false_horizon] <= 0,
            )
        )
        last_signal_index = index

    average_returns = {
        horizon: _average(
            [signal.forward_returns_percent[horizon] for signal in signals]
        )
        for horizon in forward_sessions
    }
    average_relative = {
        horizon: _average(
            [
                signal.benchmark_relative_returns_percent[horizon]
                for signal in signals
                if signal.benchmark_relative_returns_percent is not None
            ]
        )
        for horizon in forward_sessions
    }
    false_rate = (
        Decimal(sum(signal.false_breakout for signal in signals))
        / Decimal(len(signals))
        * Decimal("100")
        if signals
        else None
    )
    return BacktestReport(
        signal_count=len(signals),
        average_forward_returns_percent=average_returns,
        average_benchmark_relative_returns_percent=average_relative,
        average_maximum_adverse_excursion_percent=_average(
            [signal.maximum_adverse_excursion_percent for signal in signals]
        ),
        false_breakout_rate_percent=false_rate,
        signals=tuple(signals),
    )
