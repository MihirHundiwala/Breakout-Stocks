from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence

from app.models import TechnicalStatus
from app.providers.contracts import DailyCandle


ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


class IncompleteCandleHistoryError(ValueError):
    pass


class PersistentCandleGapError(IncompleteCandleHistoryError):
    """A successful provider fetch still omitted internal exchange sessions."""


class InsufficientListingHistoryError(IncompleteCandleHistoryError):
    """The available continuous listing history is shorter than the algorithm needs."""


@dataclass(frozen=True, slots=True)
class TechnicalAnalysisConfig:
    minimum_sessions: int = 252
    short_sma_sessions: int = 50
    medium_sma_sessions: int = 150
    long_sma_sessions: int = 200
    slope_lookback_sessions: int = 20
    range_52_week_sessions: int = 252
    range_26_week_sessions: int = 130
    minimum_high_ratio: Decimal = Decimal("0.75")
    minimum_low_ratio: Decimal = Decimal("1.25")
    maximum_26_week_high_distance: Decimal = Decimal("0.10")
    consolidation_windows: tuple[int, ...] = tuple(range(20, 121))
    minimum_base_depth: Decimal = ZERO
    # Each band is: maximum sessions, maximum body depth, maximum wick depth.
    base_depth_bands: tuple[tuple[int, Decimal, Decimal], ...] = (
        (39, Decimal("0.12"), Decimal("0.16")),
        (79, Decimal("0.15"), Decimal("0.20")),
        (120, Decimal("0.18"), Decimal("0.24")),
    )
    weekly_consolidation_windows: tuple[int, ...] = tuple(range(26, 105))
    # Completed-week bases use wider outer envelopes than daily bases.
    weekly_base_depth_bands: tuple[tuple[int, Decimal, Decimal], ...] = (
        (39, Decimal("0.25"), Decimal("0.30")),
        (59, Decimal("0.28"), Decimal("0.34")),
        (104, Decimal("0.32"), Decimal("0.38")),
    )
    weekly_maximum_base_regime_drift: Decimal = Decimal("0.12")
    weekly_minimum_resistance_touches: int = 3
    weekly_long_minimum_resistance_touches: int = 2
    weekly_long_two_touch_start: int = 40
    weekly_minimum_touch_separation: int = 3
    weekly_launch_window: int = 13
    weekly_launch_body_depth: Decimal = Decimal("0.25")
    weekly_launch_wick_depth: Decimal = Decimal("0.30")
    weekly_minimum_resistance_position: Decimal = Decimal("0.75")
    minimum_base_position: Decimal = Decimal("0.75")
    approach_lookback_sessions: int = 5
    maximum_base_regime_drift: Decimal = Decimal("0.08")
    base_range_trim_fraction: Decimal = Decimal("0.05")
    atr_sessions: int = 14
    contraction_recent_sessions: int = 10
    contraction_reference_sessions: int = 40
    return_volatility_recent_sessions: int = 10
    return_volatility_reference_sessions: int = 40
    range_recent_sessions: int = 5
    range_reference_sessions: int = 20
    maximum_atr_contraction_ratio: Decimal = Decimal("0.90")
    maximum_return_volatility_ratio: Decimal = Decimal("0.90")
    maximum_daily_range_ratio: Decimal = Decimal("0.90")
    maximum_ma_spread: Decimal = Decimal("0.04")
    weekly_contraction_recent_periods: int = 5
    weekly_contraction_reference_periods: int = 20
    weekly_fast_ema_periods: int = 5
    weekly_medium_ema_periods: int = 10
    weekly_sma_periods: int = 20
    weekly_maximum_atr_contraction_ratio: Decimal = Decimal("0.90")
    weekly_maximum_return_volatility_ratio: Decimal = Decimal("0.90")
    weekly_maximum_range_ratio: Decimal = Decimal("0.90")
    weekly_maximum_ma_spread: Decimal = Decimal("0.08")
    minimum_contraction_checks: int = 1
    fast_ema_sessions: int = 10
    medium_ema_sessions: int = 20
    pivot_left_sessions: int = 2
    pivot_right_sessions: int = 2
    resistance_percent_tolerance: Decimal = Decimal("0.0075")
    resistance_atr_tolerance: Decimal = Decimal("0.36")
    minimum_resistance_touches: int = 2
    resistance_acceptance_closes: int = 2
    minimum_touch_separation_sessions: int = 3
    resistance_pivots_use_wicks: bool = False
    maximum_resistance_dispersion: Decimal = Decimal("0.01")
    resistance_touch_full_score_count: int = 4
    resistance_separation_full_score_sessions: int = 6
    resistance_proximity_score_distance: Decimal = Decimal("0.10")
    maximum_consolidating_distance: Decimal = Decimal("0.05")
    volume_long_sessions: int = 50
    breakout_percent_buffer: Decimal = Decimal("0.003")
    breakout_atr_buffer: Decimal = Decimal("0.20")
    breakout_confirmation_percent: Decimal = Decimal("0.001")
    breakout_confirmation_atr: Decimal = Decimal("0.10")
    minimum_breakout_volume_ratio: Decimal = Decimal("1.40")
    minimum_close_location_value: Decimal = Decimal("0.70")
    maximum_breakout_extension_atr: Decimal = Decimal("1.50")
    minimum_early_recovery_volume_ratio: Decimal = Decimal("2.00")
    minimum_early_recovery_close_location: Decimal = Decimal("0.75")
    maximum_early_recovery_extension_atr: Decimal = Decimal("2.50")
    maximum_early_recovery_sma150_gap: Decimal = Decimal("0.08")
    maximum_early_recovery_sma200_decline: Decimal = Decimal("0.02")
    failure_window_sessions: int = 5
    weekly_breakout_holding_weeks: int = 3
    retest_window_sessions: int = 20
    weekly_retest_window_weeks: int = 8
    maximum_holding_extension_atr: Decimal = Decimal("3")
    maximum_holding_extension_pct: Decimal = Decimal("0.15")
    recent_resistance_extension_periods: int = 4
    maximum_recent_resistance_extension_atr: Decimal = Decimal("0.35")
    failure_percent_buffer: Decimal = Decimal("0.005")
    failure_atr_buffer: Decimal = Decimal("0.25")
    retest_touch_percent_tolerance: Decimal = Decimal("0.001")
    retest_touch_atr_tolerance: Decimal = Decimal("0.10")
    traded_value_average_sessions: int = 20
    relative_strength_average_sessions: int = 50
    relative_strength_high_sessions: int = 60
    relative_strength_near_high_floor: Decimal = Decimal("0.95")
    relative_strength_below_average_floor: Decimal = Decimal("0.95")
    stage2_close_above_sma50_full_score: Decimal = Decimal("0.10")
    stage2_sma50_above_sma150_full_score: Decimal = Decimal("0.08")
    stage2_sma150_above_sma200_full_score: Decimal = Decimal("0.06")
    stage2_sma200_slope_full_score: Decimal = Decimal("0.04")
    stage2_weight: Decimal = Decimal("20")
    relative_strength_weight: Decimal = Decimal("20")
    base_quality_weight: Decimal = Decimal("15")
    volatility_contraction_weight: Decimal = Decimal("15")
    volume_contraction_weight: Decimal = ZERO
    resistance_quality_weight: Decimal = Decimal("15")
    proximity_weight: Decimal = Decimal("10")
    closing_quality_weight: Decimal = Decimal("5")
    algorithm_version: str = "technical-v21"

    def __post_init__(self) -> None:
        if not self.consolidation_windows or any(
            window <= 0 for window in self.consolidation_windows
        ):
            raise ValueError("Consolidation windows must contain positive sessions.")
        if tuple(sorted(set(self.consolidation_windows))) != self.consolidation_windows:
            raise ValueError("Consolidation windows must be unique and ascending.")
        if not ZERO <= self.minimum_base_depth < self.maximum_base_depth < ONE:
            raise ValueError("Base-depth thresholds must be ordered within 0-1.")
        if not ZERO <= self.minimum_base_position <= ONE:
            raise ValueError("Base position must be within 0-1.")
        if self.approach_lookback_sessions < 1:
            raise ValueError("Approach lookback must be positive.")
        if not ZERO <= self.maximum_base_regime_drift < ONE:
            raise ValueError("Base regime drift must be within 0-1.")
        if not self.base_depth_bands:
            raise ValueError("Base-depth bands cannot be empty.")
        band_ends = tuple(item[0] for item in self.base_depth_bands)
        if tuple(sorted(set(band_ends))) != band_ends:
            raise ValueError("Base-depth band endpoints must be unique and ascending.")
        if band_ends[-1] < self.maximum_base_sessions:
            raise ValueError("Base-depth bands must cover every consolidation window.")
        for _, maximum_body_depth, maximum_wick_depth in self.base_depth_bands:
            if not ZERO < maximum_body_depth <= maximum_wick_depth < ONE:
                raise ValueError("Body and wick depth limits must be positive and ordered within 0-1.")
        if not self.weekly_consolidation_windows or tuple(
            sorted(set(self.weekly_consolidation_windows))
        ) != self.weekly_consolidation_windows:
            raise ValueError("Weekly consolidation windows must be unique and ascending.")
        weekly_band_ends = tuple(item[0] for item in self.weekly_base_depth_bands)
        if (
            not weekly_band_ends
            or weekly_band_ends[-1] < max(self.weekly_consolidation_windows)
        ):
            raise ValueError("Weekly depth bands must cover every weekly window.")
        if (
            self.weekly_minimum_resistance_touches < 3
            or self.weekly_long_minimum_resistance_touches < 2
            or self.weekly_long_two_touch_start
            <= min(self.weekly_consolidation_windows)
        ):
            raise ValueError("Weekly resistance-touch thresholds are invalid.")
        if self.weekly_minimum_touch_separation < 1 or self.weekly_launch_window < 4:
            raise ValueError("Weekly separation and launch windows must be positive.")
        if not (
            ZERO < self.weekly_launch_body_depth
            <= self.weekly_launch_wick_depth < ONE
            and ZERO <= self.weekly_maximum_base_regime_drift < ONE
            and ZERO <= self.weekly_minimum_resistance_position <= ONE
        ):
            raise ValueError("Weekly long-base thresholds are invalid.")
        if (
            self.weekly_contraction_recent_periods < 1
            or self.weekly_contraction_reference_periods < 1
            or self.weekly_fast_ema_periods < 1
            or self.weekly_medium_ema_periods
            < self.weekly_fast_ema_periods
            or self.weekly_sma_periods < self.weekly_medium_ema_periods
            or any(
                threshold <= ZERO
                for threshold in (
                    self.weekly_maximum_atr_contraction_ratio,
                    self.weekly_maximum_return_volatility_ratio,
                    self.weekly_maximum_range_ratio,
                    self.weekly_maximum_ma_spread,
                )
            )
        ):
            raise ValueError("Weekly contraction thresholds are invalid.")
        if not ZERO <= self.base_range_trim_fraction < Decimal("0.50"):
            raise ValueError("Base-range trimming must be within 0-0.5.")
        if self.minimum_resistance_touches < 2:
            raise ValueError("Resistance requires at least two touches.")
        if self.resistance_acceptance_closes < 1:
            raise ValueError("Resistance acceptance requires at least one close.")
        if self.minimum_touch_separation_sessions < 1:
            raise ValueError("Touch separation must be positive.")
        if self.resistance_touch_full_score_count < self.minimum_resistance_touches:
            raise ValueError("Full resistance-touch score cannot require fewer touches.")
        if self.resistance_separation_full_score_sessions < self.minimum_touch_separation_sessions:
            raise ValueError("Full separation score cannot be below minimum separation.")
        if self.resistance_proximity_score_distance <= ZERO:
            raise ValueError("Resistance proximity scoring distance must be positive.")
        if not ZERO <= self.maximum_consolidating_distance < ONE:
            raise ValueError("Consolidating distance must be within 0-1.")
        if (
            self.breakout_confirmation_percent < ZERO
            or self.breakout_confirmation_atr < ZERO
        ):
            raise ValueError("Breakout confirmation clearance cannot be negative.")
        if (
            self.retest_touch_percent_tolerance < ZERO
            or self.retest_touch_atr_tolerance < ZERO
        ):
            raise ValueError("Retest touch tolerances cannot be negative.")
        if (
            self.failure_window_sessions < 1
            or self.weekly_breakout_holding_weeks < 1
            or self.retest_window_sessions < self.failure_window_sessions
            or self.weekly_retest_window_weeks
            < self.weekly_breakout_holding_weeks
        ):
            raise ValueError("Breakout lifecycle windows must be positive and ordered.")
        if (
            self.maximum_holding_extension_atr <= ZERO
            or not ZERO < self.maximum_holding_extension_pct < ONE
            or self.recent_resistance_extension_periods < 1
            or self.maximum_recent_resistance_extension_atr <= ZERO
        ):
            raise ValueError("Breakout extension and recent-shelf limits are invalid.")
        if (
            self.minimum_early_recovery_volume_ratio <= ZERO
            or not ZERO <= self.minimum_early_recovery_close_location <= ONE
            or self.maximum_early_recovery_extension_atr <= ZERO
            or not ZERO <= self.maximum_early_recovery_sma150_gap < ONE
            or not ZERO <= self.maximum_early_recovery_sma200_decline < ONE
        ):
            raise ValueError("Early-recovery thresholds are invalid.")
        if not 1 <= self.minimum_contraction_checks <= 4:
            raise ValueError("Contraction checks must require between one and four passes.")
        if self.traded_value_average_sessions < 1:
            raise ValueError("Traded-value averaging window must be positive.")
        if self.fast_ema_sessions < 1 or self.medium_ema_sessions < self.fast_ema_sessions:
            raise ValueError("EMA windows must be positive and ordered.")
        if not (
            ZERO <= self.relative_strength_near_high_floor < ONE
            and ZERO <= self.relative_strength_below_average_floor < ONE
        ):
            raise ValueError("Relative-strength score floors must be within 0-1.")
        if any(
            scale <= ZERO
            for scale in (
                self.stage2_close_above_sma50_full_score,
                self.stage2_sma50_above_sma150_full_score,
                self.stage2_sma150_above_sma200_full_score,
                self.stage2_sma200_slope_full_score,
            )
        ):
            raise ValueError("Stage 2 score scales must be positive.")
        weights = (
            self.stage2_weight,
            self.relative_strength_weight,
            self.base_quality_weight,
            self.volatility_contraction_weight,
            self.volume_contraction_weight,
            self.resistance_quality_weight,
            self.proximity_weight,
            self.closing_quality_weight,
        )
        if any(weight < ZERO for weight in weights) or sum(weights, ZERO) != HUNDRED:
            raise ValueError("Technical score weights must be non-negative and total 100.")

    @property
    def maximum_base_sessions(self) -> int:
        return max(self.consolidation_windows)

    @property
    def maximum_base_depth(self) -> Decimal:
        return max(item[2] for item in self.base_depth_bands)

    @property
    def maximum_body_base_depth(self) -> Decimal:
        return max(item[1] for item in self.base_depth_bands)

    def base_depth_limits(self, window: int) -> tuple[Decimal, Decimal]:
        for maximum_sessions, body_depth, wick_depth in self.base_depth_bands:
            if window <= maximum_sessions:
                return body_depth, wick_depth
        raise ValueError(f"No base-depth band covers {window} sessions.")

    def weekly_base_depth_limits(self, window: int) -> tuple[Decimal, Decimal]:
        for maximum_weeks, body_depth, wick_depth in self.weekly_base_depth_bands:
            if window <= maximum_weeks:
                return body_depth, wick_depth
        raise ValueError(f"No weekly base-depth band covers {window} weeks.")

    @property
    def base_sessions(self) -> int:
        """Compatibility boundary used by the historical report."""
        return self.maximum_base_sessions

    @property
    def high_lookback_sessions(self) -> int:
        """Compatibility boundary used by the historical report."""
        return self.range_52_week_sessions


def required_candle_sessions(
    config: TechnicalAnalysisConfig = TechnicalAnalysisConfig(),
) -> int:
    return max(
        config.minimum_sessions,
        config.long_sma_sessions + config.slope_lookback_sessions,
        config.range_52_week_sessions,
        config.maximum_base_sessions
        + config.pivot_right_sessions
        + config.volume_long_sessions,
    )


@dataclass(frozen=True, slots=True)
class TechnicalAnalysisResult:
    analysis_date: date
    status: TechnicalStatus
    close_price: Decimal
    previous_close_price: Decimal
    sma50: Decimal
    sma150: Decimal
    sma200: Decimal
    high_52_week: Decimal
    low_52_week: Decimal
    high_26_week: Decimal
    setup_score: Decimal
    stage2_score: Decimal
    relative_strength_score: Decimal | None
    base_quality_score: Decimal
    volatility_contraction_score: Decimal
    volume_contraction_score: Decimal
    resistance_quality_score: Decimal
    proximity_score: Decimal
    closing_quality_score: Decimal
    consolidation_window: int | None
    consolidation_timeframe: str | None
    consolidation_start: date | None
    base_high: Decimal | None
    base_low: Decimal | None
    base_depth_pct: Decimal | None
    base_position: Decimal | None
    resistance_price: Decimal | None
    resistance_zone_lower: Decimal | None
    resistance_zone_upper: Decimal | None
    resistance_touch_count: int
    resistance_dispersion_pct: Decimal | None
    resistance_touch_dates: tuple[date, ...]
    distance_to_resistance_pct: Decimal | None
    atr14: Decimal
    atr_pct: Decimal
    atr_contraction_ratio: Decimal | None
    return_volatility_ratio: Decimal | None
    daily_range_ratio: Decimal | None
    ma_spread: Decimal
    volume_dryup_ratio: Decimal | None
    breakout_volume_ratio: Decimal | None
    distribution_day_count: int
    tightness_pass_count: int
    close_location_value: Decimal
    breakout_extension_atr: Decimal | None
    average_traded_value_20: Decimal
    rejection_reasons: tuple[str, ...]
    algorithm_version: str
    chart_evidence: tuple["TechnicalChartEvidence", ...] = ()

    @property
    def base_sessions(self) -> int | None:
        return self.consolidation_window

    @property
    def excess_return_20(self) -> Decimal:
        return ZERO

    @property
    def excess_return_60(self) -> Decimal:
        return ZERO


@dataclass(frozen=True, slots=True)
class _ResistanceCluster:
    resistance: Decimal
    rejection_ceiling: Decimal
    touch_indices: tuple[int, ...]
    touch_dates: tuple[date, ...]
    dispersion: Decimal
    latest_touch_index: int
    preinvalidated: bool = False
    marker_dates: tuple[date, ...] = ()


@dataclass(frozen=True, slots=True)
class _ContractionMeasurement:
    atr_ratio: Decimal | None
    return_volatility_ratio: Decimal | None
    range_ratio: Decimal | None
    ma_spread: Decimal
    score: Decimal
    pass_count: int


@dataclass(frozen=True, slots=True)
class _ConsolidationCandidate:
    window: int
    start: date
    base_high: Decimal
    base_low: Decimal
    depth: Decimal
    position: Decimal
    resistance: _ResistanceCluster
    base_quality_score: Decimal
    resistance_quality_score: Decimal
    candidate_score: Decimal
    tightness_pass_count: int
    contraction: _ContractionMeasurement
    breakout_date: date | None
    timeframe: str = "DAILY"
    candles: tuple[DailyCandle, ...] = ()
    resistance_atr: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class TechnicalChartEvidence:
    timeframe: str
    period_count: int
    status: TechnicalStatus
    resistance_price: Decimal
    resistance_zone_lower: Decimal
    resistance_zone_upper: Decimal
    resistance_touch_dates: tuple[date, ...]
    candles: tuple[DailyCandle, ...]


@dataclass(frozen=True, slots=True)
class _RelativeStrengthMeasurement:
    score: Decimal
    above_average: bool
    near_high_ratio: Decimal


@dataclass(frozen=True, slots=True)
class _ConsolidationSearch:
    candidate: _ConsolidationCandidate | None
    broken_candidate: _ConsolidationCandidate | None
    support_failed: bool


def _clamp(value: Decimal, lower: Decimal = ZERO, upper: Decimal = ONE) -> Decimal:
    return min(upper, max(lower, value))


def _average(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise ValueError("Cannot average an empty sequence.")
    return sum(values, start=ZERO) / Decimal(len(values))


def _median(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise ValueError("Cannot calculate the median of an empty sequence.")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def _percentile(values: Sequence[Decimal], percentile: Decimal) -> Decimal:
    if not values:
        raise ValueError("Cannot calculate a percentile of an empty sequence.")
    if not ZERO <= percentile <= ONE:
        raise ValueError("Percentile must be within 0-1.")
    ordered = sorted(values)
    index = int(Decimal(len(ordered) - 1) * percentile)
    return ordered[index]


def _body_high(candle: DailyCandle) -> Decimal:
    return max(candle.open, candle.close)


def _body_low(candle: DailyCandle) -> Decimal:
    return min(candle.open, candle.close)


def _robust_bounds(
    lows: Sequence[Decimal],
    highs: Sequence[Decimal],
    *,
    trim_fraction: Decimal,
) -> tuple[Decimal, Decimal]:
    if not lows or len(lows) != len(highs):
        raise ValueError("Robust bounds require equal non-empty price series.")
    trim_count = min(
        int(Decimal(len(lows)) * trim_fraction),
        (len(lows) - 1) // 2,
    )
    ordered_lows = sorted(lows)
    ordered_highs = sorted(highs)
    return ordered_lows[trim_count], ordered_highs[-trim_count - 1]


def _population_std(values: Sequence[Decimal]) -> Decimal:
    if len(values) < 2:
        return ZERO
    mean = _average(values)
    variance = _average([(value - mean) ** 2 for value in values])
    return variance.sqrt()


def _safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return numerator / denominator if denominator > ZERO else None


def _ema(values: Sequence[Decimal], sessions: int) -> Decimal:
    selected = values[-sessions:]
    ema = selected[0]
    multiplier = Decimal("2") / Decimal(sessions + 1)
    for value in selected[1:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _true_ranges(candles: Sequence[DailyCandle]) -> list[Decimal]:
    ranges: list[Decimal] = []
    for index, candle in enumerate(candles):
        previous_close = candles[index - 1].close if index else candle.close
        ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        )
    return ranges


def _completed_weekly_candles(
    candles: Sequence[DailyCandle],
    *,
    signal_date: date,
    include_signal_week: bool = False,
) -> tuple[DailyCandle, ...]:
    """Aggregate stored daily bars without allowing the signal week into its base."""
    grouped: dict[tuple[int, int], list[DailyCandle]] = {}
    signal_week = signal_date.isocalendar()[:2]
    for candle in candles:
        week = candle.trading_date.isocalendar()[:2]
        if week == signal_week and not include_signal_week:
            continue
        grouped.setdefault(week, []).append(candle)
    result: list[DailyCandle] = []
    for week in sorted(grouped):
        values = sorted(grouped[week], key=lambda item: item.trading_date)
        first, last = values[0], values[-1]
        result.append(
            DailyCandle(
                trading_date=last.trading_date,
                timestamp=last.timestamp,
                open=first.open,
                high=max(item.high for item in values),
                low=min(item.low for item in values),
                close=last.close,
                volume=sum(item.volume for item in values),
                open_interest=last.open_interest,
            )
        )
    return tuple(result)


def _chart_evidence(
    candidate: _ConsolidationCandidate,
    *,
    ordered: Sequence[DailyCandle],
    status: TechnicalStatus,
    config: TechnicalAnalysisConfig,
) -> TechnicalChartEvidence:
    zone_lower, zone_upper = _resistance_zone(
        candidate.resistance,
        atr14=candidate.resistance_atr,
        config=config,
    )
    if candidate.timeframe == "WEEKLY":
        chart_candles = tuple(
            item
            for item in _completed_weekly_candles(
                ordered,
                signal_date=ordered[-1].trading_date,
                include_signal_week=True,
            )
            if item.trading_date >= candidate.start
        )
    else:
        chart_candles = tuple(
            item for item in ordered if item.trading_date >= candidate.start
        )
    return TechnicalChartEvidence(
        timeframe=candidate.timeframe,
        period_count=candidate.window,
        status=status,
        resistance_price=candidate.resistance.resistance,
        resistance_zone_lower=zone_lower,
        resistance_zone_upper=zone_upper,
        resistance_touch_dates=(
            candidate.resistance.marker_dates
            or candidate.resistance.touch_dates
        ),
        candles=chart_candles,
    )


def _extend_chart_evidence_to_analysis_date(
    evidence: TechnicalChartEvidence,
    *,
    ordered: Sequence[DailyCandle],
    status: TechnicalStatus,
) -> TechnicalChartEvidence:
    """Keep the measured base fixed while showing its complete lifecycle."""
    if not evidence.candles:
        return replace(evidence, status=status)
    window_start = evidence.candles[0].trading_date
    if evidence.timeframe == "WEEKLY":
        chart_candles = tuple(
            item
            for item in _completed_weekly_candles(
                ordered,
                signal_date=ordered[-1].trading_date,
                include_signal_week=True,
            )
            if item.trading_date >= window_start
        )
    else:
        chart_candles = tuple(
            item for item in ordered if item.trading_date >= window_start
        )
    return replace(
        evidence,
        status=status,
        candles=chart_candles,
    )


def _ratio_of_recent_to_previous(
    values: Sequence[Decimal],
    *,
    recent_sessions: int,
    reference_sessions: int,
) -> Decimal | None:
    required = recent_sessions + reference_sessions
    if len(values) < required:
        return None
    recent = _average(values[-recent_sessions:])
    previous = _average(values[-required:-recent_sessions])
    return _safe_ratio(recent, previous)


def _return_volatility_ratio(
    closes: Sequence[Decimal],
    *,
    recent_sessions: int,
    reference_sessions: int,
) -> Decimal | None:
    returns = [(closes[index] / closes[index - 1]).ln() for index in range(1, len(closes))]
    required = recent_sessions + reference_sessions
    if len(returns) < required:
        return None
    recent = _population_std(returns[-recent_sessions:])
    previous = _population_std(returns[-required:-recent_sessions])
    return _safe_ratio(recent, previous)


def _contraction_measurement(
    candles: Sequence[DailyCandle],
    *,
    scale_close: Decimal,
    config: TechnicalAnalysisConfig,
    timeframe: str,
) -> _ContractionMeasurement:
    closes = [item.close for item in candles]
    true_ranges = _true_ranges(candles)
    ranges = [(item.high - item.low) / item.close for item in candles]
    if timeframe == "WEEKLY":
        atr_recent = return_recent = range_recent = (
            config.weekly_contraction_recent_periods
        )
        atr_reference = return_reference = range_reference = (
            config.weekly_contraction_reference_periods
        )
        fast_ema = config.weekly_fast_ema_periods
        medium_ema = config.weekly_medium_ema_periods
        average_periods = config.weekly_sma_periods
        maximums = (
            config.weekly_maximum_atr_contraction_ratio,
            config.weekly_maximum_return_volatility_ratio,
            config.weekly_maximum_range_ratio,
            config.weekly_maximum_ma_spread,
        )
    else:
        atr_recent = config.contraction_recent_sessions
        atr_reference = config.contraction_reference_sessions
        return_recent = config.return_volatility_recent_sessions
        return_reference = config.return_volatility_reference_sessions
        range_recent = config.range_recent_sessions
        range_reference = config.range_reference_sessions
        fast_ema = config.fast_ema_sessions
        medium_ema = config.medium_ema_sessions
        average_periods = config.short_sma_sessions
        maximums = (
            config.maximum_atr_contraction_ratio,
            config.maximum_return_volatility_ratio,
            config.maximum_daily_range_ratio,
            config.maximum_ma_spread,
        )
    atr_ratio = _ratio_of_recent_to_previous(
        true_ranges,
        recent_sessions=atr_recent,
        reference_sessions=atr_reference,
    )
    return_ratio = _return_volatility_ratio(
        closes,
        recent_sessions=return_recent,
        reference_sessions=return_reference,
    )
    range_ratio = _ratio_of_recent_to_previous(
        ranges,
        recent_sessions=range_recent,
        reference_sessions=range_reference,
    )
    ma_values = (
        _ema(closes, fast_ema),
        _ema(closes, medium_ema),
        _average(closes[-average_periods:]),
    )
    ma_spread = (max(ma_values) - min(ma_values)) / scale_close
    values = (atr_ratio, return_ratio, range_ratio, ma_spread)
    score = _average(
        [
            ONE - _clamp((value or ONE) / maximum)
            for value, maximum in zip(values, maximums, strict=True)
        ]
    )
    pass_count = sum(
        1
        for value, maximum in zip(values, maximums, strict=True)
        if value is not None and value <= maximum
    )
    return _ContractionMeasurement(
        atr_ratio=atr_ratio,
        return_volatility_ratio=return_ratio,
        range_ratio=range_ratio,
        ma_spread=ma_spread,
        score=score,
        pass_count=pass_count,
    )


def _confirmed_pivot_highs(
    candles: Sequence[DailyCandle],
    *,
    left_sessions: int,
    right_sessions: int,
) -> list[int]:
    return _confirmed_pivot_highs_by(
        candles,
        values=[_body_high(item) for item in candles],
        left_sessions=left_sessions,
        right_sessions=right_sessions,
    )


def _confirmed_pivot_highs_by(
    candles: Sequence[DailyCandle],
    *,
    values: Sequence[Decimal],
    left_sessions: int,
    right_sessions: int,
) -> list[int]:
    pivots: list[int] = []
    for index in range(left_sessions, len(candles) - right_sessions):
        current = values[index]
        if current >= max(
            values[index - left_sessions:index]
        ) and current >= max(
            values[index + 1:index + right_sessions + 1]
        ):
            pivots.append(index)
    return pivots


def _deduplicate_touches(
    indices: Sequence[int],
    *,
    candles: Sequence[DailyCandle],
    resistance: Decimal,
    minimum_separation: int,
    use_wicks: bool = False,
    use_body_or_wick: bool = False,
) -> tuple[int, ...]:
    def distance(index: int) -> Decimal:
        body_distance = abs(_body_high(candles[index]) - resistance)
        wick_distance = abs(candles[index].high - resistance)
        if use_body_or_wick:
            return min(body_distance, wick_distance)
        return wick_distance if use_wicks else body_distance

    selected: list[int] = []
    for index in sorted(indices):
        if not selected or index - selected[-1] >= minimum_separation:
            selected.append(index)
        elif distance(index) < distance(selected[-1]):
            selected[-1] = index
    return tuple(selected)


def _touches_raised_body_resistance(
    candle: DailyCandle,
    *,
    resistance: Decimal,
    tolerance: Decimal,
) -> bool:
    """A rejection may meet the shelf with its body or its upper wick."""
    return min(
        abs(_body_high(candle) - resistance),
        abs(candle.high - resistance),
    ) <= tolerance


def _extend_resistance_with_recent_bodies(
    base: Sequence[DailyCandle],
    *,
    resistance: Decimal,
    rejection_ceiling: Decimal,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
    current_close: Decimal | None,
) -> tuple[Decimal, Decimal]:
    """Let a fresh body plateau refine a shelf before calling it broken.

    The extension is deliberately local and bounded. It can absorb a marginal
    probe around the existing zone (including the open of a red rejection
    candle), but it cannot chase a decisive move far above the old shelf.
    """
    recent = base[-min(config.recent_resistance_extension_periods, len(base)):]
    recent_body_ceiling = max(_body_high(item) for item in recent)
    tolerance = max(
        resistance * config.resistance_percent_tolerance,
        atr14 * config.resistance_atr_tolerance,
    )
    half_width = max(
        resistance * config.breakout_percent_buffer,
        atr14 * config.breakout_atr_buffer,
    )
    existing_zone_upper = max(resistance + half_width, rejection_ceiling)
    existing_zone_lower = resistance - half_width
    if (
        current_close is not None
        and existing_zone_lower <= current_close <= existing_zone_upper
        and recent_body_ceiling <= existing_zone_upper + tolerance
        and recent_body_ceiling
        <= existing_zone_upper
        + atr14 * config.maximum_recent_resistance_extension_atr
    ):
        resistance = max(resistance, recent_body_ceiling)
        rejection_ceiling = max(rejection_ceiling, resistance)
    return resistance, rejection_ceiling


def _resistance_marker_dates(
    base: Sequence[DailyCandle],
    *,
    start_index: int,
    resistance: Decimal,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
) -> tuple[date, ...]:
    """Return every visible rejection while keeping touch independence separate."""
    tolerance = max(
        resistance * config.resistance_percent_tolerance,
        atr14 * config.resistance_atr_tolerance,
    )
    zone_floor = resistance - tolerance
    return tuple(
        item.trading_date
        for item in base[start_index:]
        if item.high >= zone_floor
        and item.close <= resistance
        and _body_high(item) <= resistance
    )


def _has_intervening_resistance_failure(
    candles: Sequence[DailyCandle],
    *,
    start_index: int,
    end_index: int,
    resistance: Decimal,
    rejection_ceiling: Decimal,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
) -> bool:
    """Reject shelves that conceal acceptance and a return between contacts."""
    provisional = _ResistanceCluster(
        resistance=resistance,
        rejection_ceiling=rejection_ceiling,
        touch_indices=(start_index, end_index),
        touch_dates=(
            candles[start_index].trading_date,
            candles[end_index].trading_date,
        ),
        dispersion=ZERO,
        latest_touch_index=end_index,
    )
    confirmation_ceiling = _breakout_confirmation_ceiling(
        provisional,
        atr14=atr14,
        config=config,
    )
    failure_boundary = resistance - max(
        resistance * config.failure_percent_buffer,
        atr14 * config.failure_atr_buffer,
    )
    accepted = False
    accepted_count = 0
    for candle in candles[start_index + 1:end_index]:
        if candle.close > confirmation_ceiling:
            accepted = True
            accepted_count += 1
        elif accepted and candle.close < failure_boundary:
            return True
    return accepted_count >= config.resistance_acceptance_closes


def _resistance_clusters(
    base: Sequence[DailyCandle],
    *,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
    current_close: Decimal | None = None,
) -> list[_ResistanceCluster]:
    if config.resistance_pivots_use_wicks:
        return _wick_resistance_clusters(
            base,
            atr14=atr14,
            config=config,
        )
    pivots = _confirmed_pivot_highs(
        base,
        left_sessions=config.pivot_left_sessions,
        right_sessions=config.pivot_right_sessions,
    )
    wick_pivots = _confirmed_pivot_highs_by(
        base,
        values=[item.high for item in base],
        left_sessions=config.pivot_left_sessions,
        right_sessions=config.pivot_right_sessions,
    )
    clusters: dict[tuple[int, ...], _ResistanceCluster] = {}
    for anchor_index in pivots:
        anchor = _body_high(base[anchor_index])
        tolerance = max(
            anchor * config.resistance_percent_tolerance,
            atr14 * config.resistance_atr_tolerance,
        )
        raw = [
            index for index in pivots
            if abs(_body_high(base[index]) - anchor) <= tolerance
        ]
        if len(raw) < config.minimum_resistance_touches:
            continue
        body_level = _median([_body_high(base[index]) for index in raw])
        rejection_ceiling = _median([base[index].high for index in raw])
        resistance = (body_level + rejection_ceiling) / Decimal("2")
        tolerance = max(
            resistance * config.resistance_percent_tolerance,
            atr14 * config.resistance_atr_tolerance,
        )
        raw = [
            index for index in raw
            if abs(_body_high(base[index]) - body_level) <= tolerance
        ]
        core_touches = _deduplicate_touches(
            raw,
            candles=base,
            resistance=resistance,
            minimum_separation=config.minimum_touch_separation_sessions,
        )
        if len(core_touches) < config.minimum_resistance_touches:
            continue
        core_body_prices = [_body_high(base[index]) for index in core_touches]
        core_dispersion = _population_std(core_body_prices) / _median(core_body_prices)
        if core_dispersion > config.maximum_resistance_dispersion:
            continue
        provisional_wick_ceiling = _median(
            [base[index].high for index in core_touches]
        )
        provisional_resistance = (
            _median(core_body_prices) + provisional_wick_ceiling
        ) / Decimal("2")
        preinvalidated = _has_intervening_resistance_failure(
            base,
            start_index=core_touches[0],
            end_index=core_touches[-1],
            resistance=provisional_resistance,
            rejection_ceiling=provisional_wick_ceiling,
            atr14=atr14,
            config=config,
        )
        wick_members = [
            index
            for index in wick_pivots
            if index <= core_touches[-1]
            and abs(_body_high(base[index]) - body_level) <= tolerance
        ]
        coherent_rejection_indices = set((*core_touches, *wick_members))
        shelf_start = min(coherent_rejection_indices)
        shelf_end = max(coherent_rejection_indices)
        # A horizontal resistance shelf cannot cut through accepted candle
        # bodies between its contacts. Raise it to the upper body envelope,
        # then require the independent contacts to survive at that level.
        resistance = max(
            _body_high(base[index])
            for index in range(shelf_start, shelf_end + 1)
        )
        tolerance = max(
            resistance * config.resistance_percent_tolerance,
            atr14 * config.resistance_atr_tolerance,
        )
        raised_contact_pool = [
            index
            for index in set((*pivots, *wick_pivots))
            if shelf_start <= index <= shelf_end
            and _touches_raised_body_resistance(
                base[index],
                resistance=resistance,
                tolerance=tolerance,
            )
        ]
        touches = _deduplicate_touches(
            raised_contact_pool,
            candles=base,
            resistance=resistance,
            minimum_separation=config.minimum_touch_separation_sessions,
            use_body_or_wick=True,
        )
        if len(touches) < config.minimum_resistance_touches:
            continue
        wick_prices = [base[index].high for index in touches]
        # Wicks define a zone, not the central acceptance line. A robust median
        # lets repeated rejections widen that zone without allowing one news wick
        # to move the breakout threshold on its own.
        robust_wick_ceiling = _median(wick_prices)
        resistance = max(
            resistance,
            (_median([_body_high(base[index]) for index in touches])
             + robust_wick_ceiling) / Decimal("2"),
        )
        rejection_ceiling = max(resistance, robust_wick_ceiling)
        resistance, rejection_ceiling = _extend_resistance_with_recent_bodies(
            base,
            resistance=resistance,
            rejection_ceiling=rejection_ceiling,
            atr14=atr14,
            config=config,
            current_close=current_close,
        )
        dispersion = core_dispersion
        clusters[touches] = _ResistanceCluster(
            resistance=resistance,
            rejection_ceiling=rejection_ceiling,
            touch_indices=touches,
            touch_dates=tuple(base[index].trading_date for index in touches),
            dispersion=dispersion,
            latest_touch_index=touches[-1],
            preinvalidated=preinvalidated,
            marker_dates=_resistance_marker_dates(
                base,
                start_index=shelf_start,
                resistance=resistance,
                atr14=atr14,
                config=config,
            ),
        )
    return list(clusters.values())


def _wick_resistance_clusters(
    base: Sequence[DailyCandle],
    *,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
    current_close: Decimal | None = None,
) -> list[_ResistanceCluster]:
    pivots = _confirmed_pivot_highs_by(
        base,
        values=[item.high for item in base],
        left_sessions=config.pivot_left_sessions,
        right_sessions=config.pivot_right_sessions,
    )
    clusters: dict[tuple[int, ...], _ResistanceCluster] = {}
    for anchor_index in pivots:
        anchor = base[anchor_index].high
        tolerance = max(
            anchor * config.resistance_percent_tolerance,
            atr14 * config.resistance_atr_tolerance,
        )
        raw = [
            index for index in pivots
            if abs(base[index].high - anchor) <= tolerance
        ]
        touches = _deduplicate_touches(
            raw,
            candles=base,
            resistance=anchor,
            minimum_separation=config.minimum_touch_separation_sessions,
            use_wicks=True,
        )
        if len(touches) < config.minimum_resistance_touches:
            continue
        prices = [base[index].high for index in touches]
        initial_resistance = _median(prices)
        preinvalidated = _has_intervening_resistance_failure(
            base,
            start_index=touches[0],
            end_index=touches[-1],
            resistance=initial_resistance,
            rejection_ceiling=initial_resistance,
            atr14=atr14,
            config=config,
        )
        shelf_start, shelf_end = touches[0], touches[-1]
        body_ceiling = max(
            _body_high(base[index])
            for index in range(shelf_start, shelf_end + 1)
        )
        # Weekly pivots are wick-led, so repeated wick contacts may set the
        # central line; it is still raised whenever a weekly body crossed it.
        resistance = max(initial_resistance, body_ceiling)
        tolerance = max(
            resistance * config.resistance_percent_tolerance,
            atr14 * config.resistance_atr_tolerance,
        )
        touches = _deduplicate_touches(
            [
                index
                for index in pivots
                if shelf_start <= index <= shelf_end
                and _touches_raised_body_resistance(
                    base[index],
                    resistance=resistance,
                    tolerance=tolerance,
                )
            ],
            candles=base,
            resistance=resistance,
            minimum_separation=config.minimum_touch_separation_sessions,
            use_body_or_wick=True,
        )
        if len(touches) < config.minimum_resistance_touches:
            continue
        prices = [base[index].high for index in touches]
        dispersion = _population_std(prices) / resistance
        if dispersion > config.maximum_resistance_dispersion:
            continue
        resistance, rejection_ceiling = _extend_resistance_with_recent_bodies(
            base,
            resistance=resistance,
            rejection_ceiling=max(resistance, _median(prices)),
            atr14=atr14,
            config=config,
            current_close=current_close,
        )
        clusters[touches] = _ResistanceCluster(
            resistance=resistance,
            rejection_ceiling=rejection_ceiling,
            touch_indices=touches,
            touch_dates=tuple(base[index].trading_date for index in touches),
            dispersion=dispersion,
            latest_touch_index=touches[-1],
            preinvalidated=preinvalidated,
            marker_dates=_resistance_marker_dates(
                base,
                start_index=shelf_start,
                resistance=resistance,
                atr14=atr14,
                config=config,
            ),
        )
    return list(clusters.values())


def _resistance_zone(
    cluster: _ResistanceCluster,
    *,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
) -> tuple[Decimal, Decimal]:
    half_width = max(
        cluster.resistance * config.breakout_percent_buffer,
        atr14 * config.breakout_atr_buffer,
    )
    return (
        cluster.resistance - half_width,
        max(cluster.resistance + half_width, cluster.rejection_ceiling),
    )


def _breakout_confirmation_ceiling(
    cluster: _ResistanceCluster,
    *,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
) -> Decimal:
    _, zone_upper = _resistance_zone(cluster, atr14=atr14, config=config)
    clearance = max(
        cluster.resistance * config.breakout_confirmation_percent,
        atr14 * config.breakout_confirmation_atr,
    )
    return zone_upper + clearance


def _broken_resistance_state(
    base: Sequence[DailyCandle],
    *,
    cluster: _ResistanceCluster,
    current_close: Decimal,
    current_date: date,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
) -> tuple[bool, bool, date | None]:
    if cluster.preinvalidated:
        return (
            True,
            abs(current_close - cluster.resistance) / cluster.resistance
            <= config.maximum_consolidating_distance,
            None,
        )
    confirmation_ceiling = _breakout_confirmation_ceiling(
        cluster,
        atr14=atr14,
        config=config,
    )
    # A shelf becomes actionable once the required number of separated touches
    # has established it. Later touches strengthen the same shelf, but must not
    # erase an intervening breakout or failed-breakout event.
    established_index = cluster.touch_indices[
        config.minimum_resistance_touches - 1
    ]
    post_touch = [
        (item.trading_date, item.close)
        for item in base[established_index + 1:]
    ] + [(current_date, current_close)]
    accepted_indices = [
        index
        for index, (_, close) in enumerate(post_touch)
        if close > confirmation_ceiling
    ]
    if not accepted_indices:
        return False, False, None

    failure_boundary = cluster.resistance - max(
        cluster.resistance * config.failure_percent_buffer,
        atr14 * config.failure_atr_buffer,
    )
    first_acceptance_index = accepted_indices[0]
    failure_indices = [
        index
        for index in range(first_acceptance_index + 1, len(post_touch))
        if post_touch[index][1] < failure_boundary
    ]
    support_failed = bool(
        failure_indices
        and abs(current_close - cluster.resistance) / cluster.resistance
        <= config.maximum_consolidating_distance
    )
    # Two closes above the zone confirm acceptance. One close above followed by
    # a decisive support loss is instead a failed breakout; either event retires
    # the old resistance candidate for every downstream status.
    broken = (
        len(accepted_indices) >= config.resistance_acceptance_closes
        or bool(failure_indices)
    )
    return broken, support_failed, post_touch[first_acceptance_index][0]


def _same_resistance_shelf(
    left: _ConsolidationCandidate,
    right: _ConsolidationCandidate,
    *,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
) -> bool:
    midpoint = (left.resistance.resistance + right.resistance.resistance) / Decimal("2")
    tolerance = max(
        midpoint * config.resistance_percent_tolerance,
        atr14 * config.resistance_atr_tolerance,
    )
    return abs(left.resistance.resistance - right.resistance.resistance) <= tolerance


def _select_consolidation_candidate(
    candidates: Sequence[_ConsolidationCandidate],
    *,
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
) -> _ConsolidationCandidate | None:
    shelves: list[list[_ConsolidationCandidate]] = []
    for candidate in sorted(candidates, key=lambda item: item.resistance.resistance):
        shelf = next(
            (
                group
                for group in shelves
                if _same_resistance_shelf(
                    candidate,
                    group[-1],
                    atr14=atr14,
                    config=config,
                )
            ),
            None,
        )
        if shelf is None:
            shelves.append([candidate])
        else:
            shelf.append(candidate)

    def quality_key(item: _ConsolidationCandidate) -> tuple[Decimal, int, Decimal, int]:
        return (
            item.candidate_score,
            len(item.resistance.touch_indices),
            -item.resistance.dispersion,
            item.resistance.latest_touch_index,
        )

    if not shelves:
        return None
    active_shelf = max(shelves, key=lambda group: quality_key(max(group, key=quality_key)))
    # Duration corroborates a resistance shelf only after price structure has
    # established that every candidate belongs to the same active level.
    return max(
        active_shelf,
        key=lambda item: (
            item.window,
            *quality_key(item),
        ),
    )


def _resistance_quality(
    cluster: _ResistanceCluster,
    *,
    window: int,
    current_close: Decimal,
    base_low: Decimal,
    base_high: Decimal,
    config: TechnicalAnalysisConfig,
) -> Decimal:
    touch_score = _clamp(
        Decimal(len(cluster.touch_indices) - config.minimum_resistance_touches + 1)
        / Decimal(
            config.resistance_touch_full_score_count
            - config.minimum_resistance_touches
            + 1
        )
    )
    dispersion_score = ONE - _clamp(
        cluster.dispersion / config.maximum_resistance_dispersion
    )
    separations = [
        right - left
        for left, right in zip(
            cluster.touch_indices,
            cluster.touch_indices[1:],
        )
    ]
    separation_score = _clamp(
        Decimal(min(separations, default=0))
        / Decimal(config.resistance_separation_full_score_sessions)
    )
    recency_score = ONE - _clamp(
        Decimal(window - 1 - cluster.latest_touch_index) / Decimal(window)
    )
    distance_score = ONE - _clamp(
        abs(cluster.resistance - current_close)
        / current_close
        / config.resistance_proximity_score_distance
    )
    base_range = base_high - base_low
    upper_score = (
        _clamp((cluster.resistance - base_low) / base_range)
        if base_range > ZERO
        else ZERO
    )
    return _average(
        (
            touch_score,
            dispersion_score,
            separation_score,
            recency_score,
            distance_score,
            upper_score,
        )
    )


def _base_quality(depth: Decimal, maximum_depth: Decimal) -> Decimal:
    return ONE - _clamp(depth / maximum_depth)


def _base_regime_drift(
    base: Sequence[DailyCandle],
    *,
    base_high: Decimal,
) -> Decimal:
    segment_sessions = max(1, len(base) // 3)
    first_location = _median([item.close for item in base[:segment_sessions]])
    last_location = _median([item.close for item in base[-segment_sessions:]])
    return abs(last_location - first_location) / base_high


def _is_approaching_resistance(
    candles_before_signal: Sequence[DailyCandle],
    *,
    current_close: Decimal,
    config: TechnicalAnalysisConfig,
) -> bool:
    return (
        len(candles_before_signal) >= config.approach_lookback_sessions
        and current_close
        >= candles_before_signal[-config.approach_lookback_sessions].close
    )


def _candidate_is_actionable(
    candidate: _ConsolidationCandidate | None,
    *,
    current_close: Decimal,
    candles_before_signal: Sequence[DailyCandle],
    atr14: Decimal,
    config: TechnicalAnalysisConfig,
) -> bool:
    if candidate is None:
        return False
    zone_atr = candidate.resistance_atr or atr14
    confirmation_ceiling = _breakout_confirmation_ceiling(
        candidate.resistance,
        atr14=zone_atr,
        config=config,
    )
    distance = (candidate.resistance.resistance - current_close) / candidate.resistance.resistance
    return current_close > confirmation_ceiling or (
        distance <= config.maximum_consolidating_distance
        and candidate.position >= config.minimum_base_position
        and _is_approaching_resistance(
            candles_before_signal,
            current_close=current_close,
            config=config,
        )
    )


def _broken_candidate_is_relevant(
    candidate: _ConsolidationCandidate | None,
    *,
    current_close: Decimal,
    current_date: date,
    config: TechnicalAnalysisConfig,
) -> bool:
    if candidate is None or candidate.breakout_date is None:
        return False
    zone_lower, zone_upper = _resistance_zone(
        candidate.resistance,
        atr14=candidate.resistance_atr,
        config=config,
    )
    if current_close < zone_lower:
        return False
    if (
        current_close > zone_upper
        and not _holding_extension_is_actionable(
            current_close=current_close,
            zone_upper=zone_upper,
            timeframe_atr=candidate.resistance_atr,
            config=config,
        )
    ):
        return False
    elapsed_sessions = sum(
        1
        for item in candidate.candles
        if candidate.breakout_date < item.trading_date <= current_date
    )
    if current_date > candidate.candles[-1].trading_date:
        elapsed_sessions += 1
    return _breakout_holding_active(
        timeframe=candidate.timeframe,
        breakout_date=candidate.breakout_date,
        current_date=current_date,
        sessions_elapsed=elapsed_sessions,
        config=config,
    )


def _breakout_holding_active(
    *,
    timeframe: str,
    breakout_date: date,
    current_date: date,
    sessions_elapsed: int,
    config: TechnicalAnalysisConfig,
) -> bool:
    if timeframe == "WEEKLY":
        breakout_week = breakout_date - timedelta(days=breakout_date.weekday())
        current_week = current_date - timedelta(days=current_date.weekday())
        return (
            current_week - breakout_week
        ).days // 7 <= config.weekly_breakout_holding_weeks
    return sessions_elapsed <= config.failure_window_sessions


def _breakout_retest_eligible(
    *,
    timeframe: str,
    breakout_date: date,
    current_date: date,
    sessions_elapsed: int,
    config: TechnicalAnalysisConfig,
) -> bool:
    if timeframe == "WEEKLY":
        breakout_week = breakout_date - timedelta(days=breakout_date.weekday())
        current_week = current_date - timedelta(days=current_date.weekday())
        return (
            current_week - breakout_week
        ).days // 7 <= config.weekly_retest_window_weeks
    return sessions_elapsed <= config.retest_window_sessions


def _holding_extension_is_actionable(
    *,
    current_close: Decimal,
    zone_upper: Decimal,
    timeframe_atr: Decimal,
    config: TechnicalAnalysisConfig,
) -> bool:
    extension = max(ZERO, current_close - zone_upper)
    if extension == ZERO:
        return True
    return (
        timeframe_atr > ZERO
        and extension / timeframe_atr <= config.maximum_holding_extension_atr
        and extension / zone_upper <= config.maximum_holding_extension_pct
    )


def _result_timeframe_atr(
    result: TechnicalAnalysisResult,
    *,
    fallback: Decimal,
    config: TechnicalAnalysisConfig,
) -> Decimal:
    timeframe = result.consolidation_timeframe or "DAILY"
    evidence = next(
        (item for item in result.chart_evidence if item.timeframe == timeframe),
        None,
    )
    if evidence is None or len(evidence.candles) < 2:
        return fallback
    ranges = _true_ranges(evidence.candles)
    return _average(ranges[-min(config.atr_sessions, len(ranges)):])


def _marginal_breakout_rebase(
    result: TechnicalAnalysisResult,
    *,
    ordered: Sequence[DailyCandle],
    current: DailyCandle,
    timeframe_atr: Decimal,
    config: TechnicalAnalysisConfig,
) -> TechnicalAnalysisResult | None:
    """Turn an unaccepted, marginal penetration back into consolidation."""
    if (
        result.resistance_price is None
        or result.resistance_zone_upper is None
        or timeframe_atr <= ZERO
    ):
        return None
    probe_bars = [
        item
        for item in ordered
        if result.analysis_date <= item.trading_date < current.trading_date
    ]
    if not probe_bars:
        return None
    maximum_probe_close = max(item.close for item in probe_bars)
    extension = maximum_probe_close - result.resistance_zone_upper
    if (
        extension <= ZERO
        or extension / timeframe_atr
        > config.maximum_recent_resistance_extension_atr
    ):
        return None

    resistance = max(result.resistance_price, maximum_probe_close)
    half_width = max(
        resistance * config.breakout_percent_buffer,
        timeframe_atr * config.breakout_atr_buffer,
    )
    zone_lower = resistance - half_width
    zone_upper = max(resistance + half_width, result.resistance_zone_upper)
    chart_evidence = tuple(
        replace(
            evidence,
            status=TechnicalStatus.CONSOLIDATING,
            resistance_price=resistance,
            resistance_zone_lower=zone_lower,
            resistance_zone_upper=zone_upper,
            resistance_touch_dates=tuple(
                dict.fromkeys((*evidence.resistance_touch_dates, current.trading_date))
            ),
        )
        if evidence.timeframe == (result.consolidation_timeframe or "DAILY")
        else evidence
        for evidence in result.chart_evidence
    )
    return replace(
        result,
        status=TechnicalStatus.CONSOLIDATING,
        resistance_price=resistance,
        resistance_zone_lower=zone_lower,
        resistance_zone_upper=zone_upper,
        breakout_extension_atr=None,
        rejection_reasons=(),
        chart_evidence=chart_evidence,
    )


def _choose_consolidation(
    candles_before_signal: Sequence[DailyCandle],
    *,
    current_close: Decimal,
    current_date: date,
    atr14: Decimal,
    contraction: _ContractionMeasurement,
    config: TechnicalAnalysisConfig,
    timeframe: str = "DAILY",
    require_launch_area: bool = False,
) -> _ConsolidationSearch:
    candidates: list[_ConsolidationCandidate] = []
    broken_candidates: list[_ConsolidationCandidate] = []
    support_failed = False
    for window in config.consolidation_windows:
        if len(candles_before_signal) < window:
            continue
        base = candles_before_signal[-window:]
        base_low, base_high = _robust_bounds(
            [_body_low(item) for item in base],
            [_body_high(item) for item in base],
            trim_fraction=config.base_range_trim_fraction,
        )
        if base_high <= ZERO or base_high == base_low:
            continue
        depth = (base_high - base_low) / base_high
        maximum_body_depth, maximum_wick_depth = (
            config.base_depth_limits(window)
        )
        wick_low, wick_high = _robust_bounds(
            [item.low for item in base],
            [item.high for item in base],
            trim_fraction=config.base_range_trim_fraction,
        )
        if wick_high <= ZERO or wick_high == wick_low:
            continue
        wick_depth = (wick_high - wick_low) / wick_high
        if wick_depth > maximum_wick_depth:
            continue
        body_depth = depth
        if (
            body_depth > maximum_body_depth
            or _base_regime_drift(base, base_high=base_high)
            > config.maximum_base_regime_drift
            or contraction.pass_count < config.minimum_contraction_checks
        ):
            continue
        if require_launch_area:
            launch = base[-min(config.weekly_launch_window, len(base)):]
            launch_body_low, launch_body_high = _robust_bounds(
                [_body_low(item) for item in launch],
                [_body_high(item) for item in launch],
                trim_fraction=ZERO,
            )
            launch_wick_low, launch_wick_high = _robust_bounds(
                [item.low for item in launch],
                [item.high for item in launch],
                trim_fraction=ZERO,
            )
            if (
                (launch_body_high - launch_body_low) / launch_body_high
                > config.weekly_launch_body_depth
                or (launch_wick_high - launch_wick_low) / launch_wick_high
                > config.weekly_launch_wick_depth
            ):
                continue
        position = (current_close - base_low) / (base_high - base_low)
        base_score = _base_quality(depth, maximum_body_depth)
        cluster_config = config
        if timeframe == "WEEKLY" and window >= config.weekly_long_two_touch_start:
            cluster_config = replace(
                config,
                minimum_resistance_touches=(
                    config.weekly_long_minimum_resistance_touches
                ),
            )
        for cluster in _resistance_clusters(
            base,
            atr14=atr14,
            config=cluster_config,
            current_close=current_close,
        ):
            if (
                timeframe == "WEEKLY"
                and (cluster.resistance - base_low) / (base_high - base_low)
                < config.weekly_minimum_resistance_position
            ):
                continue
            broken, failed, breakout_date = _broken_resistance_state(
                base,
                cluster=cluster,
                current_close=current_close,
                current_date=current_date,
                atr14=atr14,
                config=cluster_config,
            )
            support_failed = support_failed or failed
            resistance_score = _resistance_quality(
                cluster,
                window=window,
                current_close=current_close,
                base_low=base_low,
                base_high=base_high,
                config=cluster_config,
            )
            position_score = _clamp(position)
            # Accepted body range, separate wick range, and contraction select a base.
            # Volume is deliberately reserved for breakout confirmation.
            candidate_score = _average(
                (
                    base_score,
                    contraction.score,
                    resistance_score,
                    position_score,
                )
            )
            candidate = _ConsolidationCandidate(
                window=window,
                start=base[0].trading_date,
                base_high=base_high,
                base_low=base_low,
                depth=depth,
                position=position,
                resistance=cluster,
                base_quality_score=base_score,
                resistance_quality_score=resistance_score,
                candidate_score=candidate_score,
                tightness_pass_count=contraction.pass_count,
                contraction=contraction,
                breakout_date=breakout_date if broken else None,
                timeframe=timeframe,
                candles=tuple(base),
                resistance_atr=atr14,
            )
            if broken:
                if not failed:
                    broken_candidates.append(candidate)
                continue
            candidates.append(candidate)
    return _ConsolidationSearch(
        candidate=_select_consolidation_candidate(
            candidates,
            atr14=atr14,
            config=config,
        ),
        broken_candidate=_select_consolidation_candidate(
            broken_candidates,
            atr14=atr14,
            config=config,
        ),
        support_failed=support_failed,
    )


def _stage2(
    closes: Sequence[Decimal],
    highs: Sequence[Decimal],
    lows: Sequence[Decimal],
    *,
    config: TechnicalAnalysisConfig,
) -> tuple[bool, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    close = closes[-1]
    sma50 = _average(closes[-config.short_sma_sessions:])
    sma150 = _average(closes[-config.medium_sma_sessions:])
    sma200 = _average(closes[-config.long_sma_sessions:])
    prior_sma200 = _average(
        closes[
            -config.long_sma_sessions - config.slope_lookback_sessions:
            -config.slope_lookback_sessions
        ]
    )
    high_52_week = max(highs[-config.range_52_week_sessions:])
    low_52_week = min(lows[-config.range_52_week_sessions:])
    confirmed = (
        close > sma50 > sma150 > sma200
        and sma200 > prior_sma200
        and close >= high_52_week * config.minimum_high_ratio
        and close >= low_52_week * config.minimum_low_ratio
    )
    components = (
        _clamp((close / sma50 - ONE) / config.stage2_close_above_sma50_full_score),
        _clamp((sma50 / sma150 - ONE) / config.stage2_sma50_above_sma150_full_score),
        _clamp((sma150 / sma200 - ONE) / config.stage2_sma150_above_sma200_full_score),
        _clamp((sma200 / prior_sma200 - ONE) / config.stage2_sma200_slope_full_score),
        _clamp((close / high_52_week - config.minimum_high_ratio) / (ONE - config.minimum_high_ratio)),
    )
    return confirmed, _average(components), sma50, sma150, sma200, high_52_week, low_52_week


def _early_recovery_structure(
    closes: Sequence[Decimal],
    *,
    sma50: Decimal,
    sma150: Decimal,
    sma200: Decimal,
    high_52_week: Decimal,
    low_52_week: Decimal,
    config: TechnicalAnalysisConfig,
) -> bool:
    close = closes[-1]
    prior_sma50 = _average(
        closes[
            -config.short_sma_sessions - config.slope_lookback_sessions:
            -config.slope_lookback_sessions
        ]
    )
    prior_sma200 = _average(
        closes[
            -config.long_sma_sessions - config.slope_lookback_sessions:
            -config.slope_lookback_sessions
        ]
    )
    return (
        close > sma50 > sma150
        and close > sma200
        and sma50 > prior_sma50
        and sma150
        >= sma200 * (ONE - config.maximum_early_recovery_sma150_gap)
        and sma200
        >= prior_sma200 * (ONE - config.maximum_early_recovery_sma200_decline)
        and close >= high_52_week * config.minimum_high_ratio
        and close >= low_52_week * config.minimum_low_ratio
    )


def _relative_strength_score(
    stock_candles: Sequence[DailyCandle],
    benchmark_candles: Sequence[DailyCandle] | None,
    *,
    config: TechnicalAnalysisConfig,
) -> _RelativeStrengthMeasurement | None:
    if not benchmark_candles:
        return None
    benchmark_by_date = {item.trading_date: item.close for item in benchmark_candles}
    if len(benchmark_by_date) != len(benchmark_candles):
        return None
    aligned = [
        (item.close, benchmark_by_date[item.trading_date])
        for item in stock_candles
        if item.trading_date in benchmark_by_date
        and benchmark_by_date[item.trading_date] > ZERO
    ]
    required = max(
        config.relative_strength_average_sessions,
        config.relative_strength_high_sessions,
    )
    if len(aligned) < required or stock_candles[-1].trading_date not in benchmark_by_date:
        return None
    ratios = [stock / benchmark for stock, benchmark in aligned]
    current = ratios[-1]
    average = _average(ratios[-config.relative_strength_average_sessions:])
    near_high = current / max(ratios[-config.relative_strength_high_sessions:])
    above_score = (
        ONE
        if current > average
        else _clamp(
            (current / average - config.relative_strength_below_average_floor)
            / (ONE - config.relative_strength_below_average_floor)
        )
    )
    near_high_score = _clamp(
        (near_high - config.relative_strength_near_high_floor)
        / (ONE - config.relative_strength_near_high_floor)
    )
    return _RelativeStrengthMeasurement(
        score=_average((above_score, near_high_score)),
        above_average=current > average,
        near_high_ratio=near_high,
    )


def _weighted_setup_score(
    *,
    stage2_score: Decimal,
    relative_strength_score: Decimal | None,
    base_quality_score: Decimal,
    volatility_contraction_score: Decimal,
    volume_contraction_score: Decimal,
    resistance_quality_score: Decimal,
    proximity_score: Decimal,
    closing_quality_score: Decimal,
    config: TechnicalAnalysisConfig,
) -> Decimal:
    components = [
        (stage2_score, config.stage2_weight),
        (base_quality_score, config.base_quality_weight),
        (volatility_contraction_score, config.volatility_contraction_weight),
        (volume_contraction_score, config.volume_contraction_weight),
        (resistance_quality_score, config.resistance_quality_weight),
        (proximity_score, config.proximity_weight),
        (closing_quality_score, config.closing_quality_weight),
    ]
    if relative_strength_score is not None:
        components.append((relative_strength_score, config.relative_strength_weight))
    active_weight = sum((weight for _, weight in components), ZERO)
    if active_weight == ZERO:
        return ZERO
    return sum((score * weight for score, weight in components), ZERO) / active_weight * HUNDRED


def _analyze_latest(
    ordered: Sequence[DailyCandle],
    *,
    benchmark_candles: Sequence[DailyCandle] | None,
    config: TechnicalAnalysisConfig,
    detect_failure: bool,
    timeframe_filter: str | None = None,
) -> TechnicalAnalysisResult:
    closes = [item.close for item in ordered]
    highs = [item.high for item in ordered]
    lows = [item.low for item in ordered]
    current = ordered[-1]
    previous = ordered[-2]
    prior = ordered[:-1]
    stage2, stage2_score, sma50, sma150, sma200, high_52_week, low_52_week = _stage2(
        closes, highs, lows, config=config
    )
    stage2_before_signal, *_ = _stage2(
        closes[:-1],
        highs[:-1],
        lows[:-1],
        config=config,
    )
    early_recovery_structure = _early_recovery_structure(
        closes,
        sma50=sma50,
        sma150=sma150,
        sma200=sma200,
        high_52_week=high_52_week,
        low_52_week=low_52_week,
        config=config,
    )
    high_26_week = _percentile(
        [item.high for item in ordered[-config.range_26_week_sessions:]],
        Decimal("0.98"),
    )
    near_26_week_high = (
        (high_26_week - current.close) / high_26_week
        <= config.maximum_26_week_high_distance
    )
    true_ranges = _true_ranges(prior)
    atr14 = _average(true_ranges[-config.atr_sessions:])
    atr_pct = atr14 / current.close
    daily_contraction = _contraction_measurement(
        prior,
        scale_close=current.close,
        config=config,
        timeframe="DAILY",
    )

    prior_volumes = [Decimal(item.volume) for item in prior]
    average_volume_50 = _average(prior_volumes[-config.volume_long_sessions:])
    breakout_volume_ratio = _safe_ratio(Decimal(current.volume), average_volume_50)
    volume_score = ZERO
    traded_values = [item.close * Decimal(item.volume) for item in ordered]
    average_traded_value_20 = _average(
        traded_values[-config.traded_value_average_sessions:]
    )
    relative_strength = _relative_strength_score(
        ordered, benchmark_candles, config=config
    )
    relative_strength_score = (
        relative_strength.score if relative_strength is not None else None
    )
    daily_search = _choose_consolidation(
        prior,
        current_close=current.close,
        current_date=current.trading_date,
        atr14=atr14,
        contraction=daily_contraction,
        config=config,
    )
    completed_weeks = _completed_weekly_candles(
        prior,
        signal_date=current.trading_date,
    )
    weekly_search = _ConsolidationSearch(
        candidate=None,
        broken_candidate=None,
        support_failed=False,
    )
    if len(completed_weeks) >= min(config.weekly_consolidation_windows):
        weekly_config = replace(
            config,
            consolidation_windows=config.weekly_consolidation_windows,
            base_depth_bands=config.weekly_base_depth_bands,
            maximum_base_regime_drift=config.weekly_maximum_base_regime_drift,
            pivot_left_sessions=1,
            pivot_right_sessions=1,
            minimum_resistance_touches=config.weekly_minimum_resistance_touches,
            minimum_touch_separation_sessions=config.weekly_minimum_touch_separation,
            resistance_pivots_use_wicks=True,
            resistance_touch_full_score_count=max(
                config.resistance_touch_full_score_count,
                config.weekly_minimum_resistance_touches + 1,
            ),
            resistance_separation_full_score_sessions=4,
        )
        weekly_atr = _average(
            _true_ranges(completed_weeks)[-min(config.atr_sessions, len(completed_weeks)):]
        )
        weekly_contraction = _contraction_measurement(
            completed_weeks,
            scale_close=completed_weeks[-1].close,
            config=config,
            timeframe="WEEKLY",
        )
        weekly_search = _choose_consolidation(
            completed_weeks,
            current_close=current.close,
            current_date=current.trading_date,
            atr14=weekly_atr,
            contraction=weekly_contraction,
            config=weekly_config,
            timeframe="WEEKLY",
            require_launch_area=True,
        )

    empty_search = _ConsolidationSearch(
        candidate=None,
        broken_candidate=None,
        support_failed=False,
    )
    if timeframe_filter == "DAILY":
        weekly_search = empty_search
    elif timeframe_filter == "WEEKLY":
        daily_search = empty_search
    elif timeframe_filter is not None:
        raise ValueError(f"Unsupported timeframe filter: {timeframe_filter}")

    daily_actionable = _candidate_is_actionable(
        daily_search.candidate,
        current_close=current.close,
        candles_before_signal=prior,
        atr14=atr14,
        config=config,
    )
    weekly_actionable = _candidate_is_actionable(
        weekly_search.candidate,
        current_close=current.close,
        candles_before_signal=prior,
        atr14=atr14,
        config=config,
    )
    weekly_broken_relevant = _broken_candidate_is_relevant(
        weekly_search.broken_candidate,
        current_close=current.close,
        current_date=current.trading_date,
        config=config,
    )
    candidate_is_broken = False
    if weekly_actionable:
        consolidation_search = weekly_search
    elif daily_actionable:
        consolidation_search = daily_search
    elif weekly_broken_relevant:
        consolidation_search = weekly_search
        candidate_is_broken = True
    elif daily_search.candidate is not None:
        consolidation_search = daily_search
    else:
        consolidation_search = weekly_search
    candidate = (
        consolidation_search.broken_candidate
        if candidate_is_broken
        else consolidation_search.candidate
    )
    selected_contraction = (
        candidate.contraction if candidate is not None else daily_contraction
    )

    candle_range = current.high - current.low
    close_location_value = (
        (current.close - current.low) / candle_range
        if candle_range > ZERO
        else ZERO
    )
    rejection_reasons: list[str] = []
    if not stage2:
        rejection_reasons.append("NOT_CONFIRMED_STAGE2")
    if not near_26_week_high:
        rejection_reasons.append("TOO_FAR_FROM_26_WEEK_HIGH")
    if relative_strength is None:
        rejection_reasons.append("RELATIVE_STRENGTH_UNAVAILABLE")
    elif (
        not relative_strength.above_average
        or relative_strength.near_high_ratio
        < config.relative_strength_near_high_floor
    ):
        rejection_reasons.append("WEAK_RELATIVE_STRENGTH")
    if candidate is None:
        rejection_reasons.append("NO_TIGHT_RESISTANCE_CONSOLIDATION")
    if daily_search.support_failed or weekly_search.support_failed:
        rejection_reasons.append("BREAKOUT_SUPPORT_FAILED")

    base_score = candidate.base_quality_score if candidate else ZERO
    resistance_score = candidate.resistance_quality_score if candidate else ZERO
    distribution_count = 0
    distance = (
        (candidate.resistance.resistance - current.close)
        / candidate.resistance.resistance
        if candidate
        else None
    )
    proximity_score = (
        ONE - _clamp(
            abs(distance) / config.maximum_consolidating_distance
        )
        if distance is not None
        else ZERO
    )
    closing_score = _clamp(close_location_value)
    candidate_zone = (
        _resistance_zone(
            candidate.resistance,
            atr14=candidate.resistance_atr or atr14,
            config=config,
        )
        if candidate is not None
        else None
    )
    breakout_extension = (
        (
            current.close
            - candidate_zone[1]
        )
        / (candidate.resistance_atr or atr14)
        if (
            candidate_zone is not None
            and candidate is not None
            and (candidate.resistance_atr or atr14) > ZERO
        )
        else None
    )
    setup_score = _weighted_setup_score(
        stage2_score=stage2_score,
        relative_strength_score=relative_strength_score,
        base_quality_score=base_score,
        volatility_contraction_score=selected_contraction.score,
        volume_contraction_score=volume_score,
        resistance_quality_score=resistance_score,
        proximity_score=proximity_score,
        closing_quality_score=closing_score,
        config=config,
    )

    status = TechnicalStatus.NO_SETUP
    resistance_zone_lower: Decimal | None = None
    resistance_zone_upper: Decimal | None = None
    price_breakout = False
    if candidate is not None:
        resistance = candidate.resistance.resistance
        resistance_zone_lower, resistance_zone_upper = _resistance_zone(
            candidate.resistance,
            atr14=candidate.resistance_atr or atr14,
            config=config,
        )
        price_breakout = current.close > _breakout_confirmation_ceiling(
            candidate.resistance,
            atr14=candidate.resistance_atr or atr14,
            config=config,
        )
        if (
            price_breakout
            and not stage2_before_signal
            and "NOT_CONFIRMED_STAGE2" not in rejection_reasons
        ):
            rejection_reasons.insert(0, "NOT_CONFIRMED_STAGE2")
    hard_rejected = bool(rejection_reasons)
    if candidate is not None and not hard_rejected:
        if candidate_is_broken:
            retest_tolerance = max(
                candidate.resistance.resistance
                * config.retest_touch_percent_tolerance,
                atr14 * config.retest_touch_atr_tolerance,
            )
            if (
                current.low <= resistance_zone_upper + retest_tolerance
                and current.close >= resistance_zone_lower
            ):
                status = TechnicalStatus.RETEST
            elif current.close > resistance_zone_upper:
                status = TechnicalStatus.BREAKOUT_HOLDING
            else:
                rejection_reasons.append("BREAKOUT_SUPPORT_FAILED")
        elif price_breakout:
            strong_volume = (
                breakout_volume_ratio is not None
                and breakout_volume_ratio >= config.minimum_breakout_volume_ratio
            )
            if not strong_volume:
                rejection_reasons.append("WEAK_BREAKOUT_VOLUME")
            status = (
                TechnicalStatus.BREAKOUT
                if strong_volume
                else TechnicalStatus.WEAK_BREAKOUT
            )
        elif (
            distance is not None
            and distance <= config.maximum_consolidating_distance
            and candidate.position >= config.minimum_base_position
            and _is_approaching_resistance(
                prior,
                current_close=current.close,
                config=config,
            )
        ):
            status = TechnicalStatus.CONSOLIDATING
        else:
            rejection_reasons.append("NOT_APPROACHING_RESISTANCE")
    elif (
        candidate is not None
        and price_breakout
        and rejection_reasons == ["NOT_CONFIRMED_STAGE2"]
        and early_recovery_structure
        and breakout_volume_ratio is not None
        and breakout_volume_ratio
        >= config.minimum_early_recovery_volume_ratio
        and close_location_value
        >= config.minimum_early_recovery_close_location
        and breakout_extension is not None
        and breakout_extension
        <= config.maximum_early_recovery_extension_atr
    ):
        status = TechnicalStatus.EARLY_RECOVERY_BREAKOUT
        rejection_reasons.clear()

    setup_context: TechnicalAnalysisResult | None = None
    if (
        detect_failure
        and candidate is None
        and status == TechnicalStatus.NO_SETUP
        and set(rejection_reasons) == {"NO_TIGHT_RESISTANCE_CONSOLIDATION"}
        and stage2_before_signal
    ):
        weekly_cutoff = current.trading_date - timedelta(
            weeks=config.weekly_breakout_holding_weeks
        )
        for sessions_ago in range(1, len(ordered)):
            if len(ordered) - sessions_ago < config.minimum_sessions:
                break
            prior_date = ordered[-sessions_ago - 1].trading_date
            if (
                sessions_ago > config.failure_window_sessions
                and prior_date < weekly_cutoff
            ):
                break
            previous_result = _analyze_latest(
                ordered[:-sessions_ago],
                benchmark_candles=benchmark_candles,
                config=config,
                detect_failure=False,
                timeframe_filter=timeframe_filter,
            )
            if (
                previous_result.status != TechnicalStatus.CONSOLIDATING
                or previous_result.resistance_price is None
                or previous_result.resistance_zone_upper is None
                or not _breakout_holding_active(
                    timeframe=(
                        previous_result.consolidation_timeframe or "DAILY"
                    ),
                    breakout_date=previous_result.analysis_date,
                    current_date=current.trading_date,
                    sessions_elapsed=sessions_ago,
                    config=config,
                )
            ):
                continue
            confirmation_ceiling = previous_result.resistance_zone_upper + max(
                previous_result.resistance_price
                * config.breakout_confirmation_percent,
                atr14 * config.breakout_confirmation_atr,
            )
            if current.close <= confirmation_ceiling:
                continue
            breakout_extension = (
                current.close - previous_result.resistance_zone_upper
            ) / atr14
            strong_volume = (
                breakout_volume_ratio is not None
                and breakout_volume_ratio
                >= config.minimum_breakout_volume_ratio
            )
            rejection_reasons.clear()
            if not strong_volume:
                rejection_reasons.append("WEAK_BREAKOUT_VOLUME")
            status = (
                TechnicalStatus.BREAKOUT
                if strong_volume
                else TechnicalStatus.WEAK_BREAKOUT
            )
            setup_context = previous_result
            break

    breakout_context: TechnicalAnalysisResult | None = None
    if detect_failure:
        weekly_cutoff = current.trading_date - timedelta(
            weeks=config.weekly_retest_window_weeks
        )
        for sessions_ago in range(1, len(ordered)):
            if len(ordered) - sessions_ago < config.minimum_sessions:
                break
            prior_date = ordered[-sessions_ago - 1].trading_date
            if (
                sessions_ago > config.retest_window_sessions
                and prior_date < weekly_cutoff
            ):
                break
            previous_result = _analyze_latest(
                ordered[:-sessions_ago],
                benchmark_candles=benchmark_candles,
                config=config,
                detect_failure=False,
                timeframe_filter=timeframe_filter,
            )
            if "BREAKOUT_SUPPORT_FAILED" in previous_result.rejection_reasons:
                break
            if previous_result.status not in {
                TechnicalStatus.BREAKOUT,
                TechnicalStatus.EARLY_RECOVERY_BREAKOUT,
                TechnicalStatus.WEAK_BREAKOUT,
            } or previous_result.resistance_price is None:
                continue
            if not _breakout_retest_eligible(
                timeframe=previous_result.consolidation_timeframe or "DAILY",
                breakout_date=previous_result.analysis_date,
                current_date=current.trading_date,
                sessions_elapsed=sessions_ago,
                config=config,
            ):
                continue
            lifecycle_atr = _result_timeframe_atr(
                previous_result,
                fallback=atr14,
                config=config,
            )
            if candidate is not None:
                midpoint = (
                    candidate.resistance.resistance
                    + previous_result.resistance_price
                ) / Decimal("2")
                shelf_tolerance = max(
                    midpoint * config.resistance_percent_tolerance,
                    lifecycle_atr * config.resistance_atr_tolerance,
                )
                if (
                    abs(
                        candidate.resistance.resistance
                        - previous_result.resistance_price
                    )
                    > shelf_tolerance
                ):
                    continue
            previous_zone_lower = previous_result.resistance_zone_lower
            previous_zone_upper = previous_result.resistance_zone_upper
            if previous_zone_lower is None or previous_zone_upper is None:
                continue
            failure_boundary = previous_result.resistance_price - max(
                previous_result.resistance_price
                * config.failure_percent_buffer,
                lifecycle_atr * config.failure_atr_buffer,
            )
            if current.close < failure_boundary:
                status = TechnicalStatus.NO_SETUP
                rejection_reasons.append("BREAKOUT_SUPPORT_FAILED")
            # The breakout session already qualified trend and relative
            # strength. Reapplying those gates after a pullback can hide the
            # very zone contact that defines a retest.
            elif (
                current.low
                <= previous_zone_upper
                + max(
                    previous_result.resistance_price
                    * config.retest_touch_percent_tolerance,
                    lifecycle_atr * config.retest_touch_atr_tolerance,
                )
                and current.close >= previous_zone_lower
            ):
                rebased_context = _marginal_breakout_rebase(
                    previous_result,
                    ordered=ordered,
                    current=current,
                    timeframe_atr=lifecycle_atr,
                    config=config,
                )
                status = (
                    TechnicalStatus.CONSOLIDATING
                    if rebased_context is not None
                    else TechnicalStatus.RETEST
                )
                breakout_context = rebased_context or previous_result
                rejection_reasons.clear()
            elif (
                current.close > previous_zone_upper
                and _breakout_holding_active(
                    timeframe=(
                        previous_result.consolidation_timeframe or "DAILY"
                    ),
                    breakout_date=previous_result.analysis_date,
                    current_date=current.trading_date,
                    sessions_elapsed=sessions_ago,
                    config=config,
                )
                and _holding_extension_is_actionable(
                    current_close=current.close,
                    zone_upper=previous_zone_upper,
                    timeframe_atr=lifecycle_atr,
                    config=config,
                )
            ):
                status = TechnicalStatus.BREAKOUT_HOLDING
                breakout_context = previous_result
                rejection_reasons.clear()
            elif current.close > previous_zone_upper:
                status = TechnicalStatus.NO_SETUP
                breakout_context = None
                rejection_reasons.clear()
                if _breakout_holding_active(
                    timeframe=(
                        previous_result.consolidation_timeframe or "DAILY"
                    ),
                    breakout_date=previous_result.analysis_date,
                    current_date=current.trading_date,
                    sessions_elapsed=sessions_ago,
                    config=config,
                ):
                    rejection_reasons.append("BREAKOUT_OVEREXTENDED")
            break

    context = breakout_context or setup_context
    context_resistance = (
        context.resistance_price
        if context is not None
        else (candidate.resistance.resistance if candidate else None)
    )
    if context is not None:
        resistance_zone_lower = context.resistance_zone_lower
        resistance_zone_upper = context.resistance_zone_upper
        distance = (
            (context.resistance_price - current.close)
            / context.resistance_price
            if context.resistance_price is not None
            else None
        )

    chart_evidence: tuple[TechnicalChartEvidence, ...] = ()
    if status != TechnicalStatus.NO_SETUP:
        if context is not None:
            chart_evidence = tuple(
                _extend_chart_evidence_to_analysis_date(
                    evidence,
                    ordered=ordered,
                    status=status,
                )
                for evidence in context.chart_evidence
            )
        else:
            evidence_candidates: list[_ConsolidationCandidate] = []
            for active_candidate, broken_candidate, actionable in (
                (
                    daily_search.candidate,
                    daily_search.broken_candidate,
                    daily_actionable,
                ),
                (
                    weekly_search.candidate,
                    weekly_search.broken_candidate,
                    weekly_actionable,
                ),
            ):
                if active_candidate is not None and actionable:
                    evidence_candidates.append(active_candidate)
                elif broken_candidate is not None and broken_candidate is candidate:
                    evidence_candidates.append(broken_candidate)
            chart_evidence = tuple(
                _chart_evidence(
                    item,
                    ordered=ordered,
                    status=status,
                    config=config,
                )
                for item in evidence_candidates
            )

    return TechnicalAnalysisResult(
        analysis_date=current.trading_date,
        status=status,
        close_price=current.close,
        previous_close_price=previous.close,
        sma50=sma50,
        sma150=sma150,
        sma200=sma200,
        high_52_week=high_52_week,
        low_52_week=low_52_week,
        high_26_week=high_26_week,
        setup_score=setup_score,
        stage2_score=stage2_score,
        relative_strength_score=relative_strength_score,
        base_quality_score=base_score,
        volatility_contraction_score=(
            context.volatility_contraction_score
            if context is not None
            else selected_contraction.score
        ),
        volume_contraction_score=volume_score,
        resistance_quality_score=resistance_score,
        proximity_score=proximity_score,
        closing_quality_score=closing_score,
        consolidation_window=(
            context.consolidation_window
            if context is not None
            else (candidate.window if candidate else None)
        ),
        consolidation_timeframe=(
            context.consolidation_timeframe
            if context is not None
            else (candidate.timeframe if candidate else None)
        ),
        consolidation_start=(
            context.consolidation_start
            if context is not None
            else (candidate.start if candidate else None)
        ),
        base_high=(
            context.base_high
            if context is not None
            else (candidate.base_high if candidate else None)
        ),
        base_low=(
            context.base_low
            if context is not None
            else (candidate.base_low if candidate else None)
        ),
        base_depth_pct=(
            context.base_depth_pct
            if context is not None
            else (candidate.depth if candidate else None)
        ),
        base_position=(
            context.base_position
            if context is not None
            else (candidate.position if candidate else None)
        ),
        resistance_price=context_resistance,
        resistance_zone_lower=resistance_zone_lower,
        resistance_zone_upper=resistance_zone_upper,
        resistance_touch_count=(
            context.resistance_touch_count
            if context is not None
            else (len(candidate.resistance.touch_indices) if candidate else 0)
        ),
        resistance_dispersion_pct=(
            context.resistance_dispersion_pct
            if context is not None
            else (candidate.resistance.dispersion if candidate else None)
        ),
        resistance_touch_dates=(
            context.resistance_touch_dates
            if context is not None
            else (candidate.resistance.touch_dates if candidate else ())
        ),
        distance_to_resistance_pct=distance,
        atr14=atr14,
        atr_pct=atr_pct,
        atr_contraction_ratio=(
            context.atr_contraction_ratio
            if context is not None
            else selected_contraction.atr_ratio
        ),
        return_volatility_ratio=(
            context.return_volatility_ratio
            if context is not None
            else selected_contraction.return_volatility_ratio
        ),
        daily_range_ratio=(
            context.daily_range_ratio
            if context is not None
            else selected_contraction.range_ratio
        ),
        ma_spread=(
            context.ma_spread
            if context is not None
            else selected_contraction.ma_spread
        ),
        volume_dryup_ratio=None,
        breakout_volume_ratio=breakout_volume_ratio,
        distribution_day_count=distribution_count,
        tightness_pass_count=(
            context.tightness_pass_count
            if context is not None
            else (
                candidate.tightness_pass_count
                if candidate
                else daily_contraction.pass_count
            )
        ),
        close_location_value=close_location_value,
        breakout_extension_atr=breakout_extension,
        average_traded_value_20=average_traded_value_20,
        rejection_reasons=tuple(dict.fromkeys(rejection_reasons)),
        algorithm_version=config.algorithm_version,
        chart_evidence=chart_evidence,
    )


def analyze_technical_setup(
    candles: Sequence[DailyCandle],
    *,
    benchmark_candles: Sequence[DailyCandle] | None = None,
    target_session: date,
    expected_sessions: Sequence[date],
    config: TechnicalAnalysisConfig = TechnicalAnalysisConfig(),
) -> TechnicalAnalysisResult:
    all_ordered = sorted(candles, key=lambda candle: candle.trading_date)
    all_dates = [candle.trading_date for candle in all_ordered]
    if len(all_dates) != len(set(all_dates)):
        raise IncompleteCandleHistoryError("Duplicate trading sessions were supplied.")
    # Point-in-time analysis deliberately ignores later candles. This makes the
    # API safe for backtests and prevents future rows from changing a past result.
    ordered = [
        candle for candle in all_ordered
        if candle.trading_date <= target_session
    ]
    dates = [candle.trading_date for candle in ordered]
    if not dates or dates[-1] != target_session:
        raise IncompleteCandleHistoryError("The target session candle is missing.")
    missing = {
        session for session in expected_sessions
        if session <= target_session
    }.difference(dates)
    if missing:
        raise IncompleteCandleHistoryError("Expected trading sessions are missing.")
    if any(
        item.open <= ZERO
        or item.high <= ZERO
        or item.low <= ZERO
        or item.close <= ZERO
        or item.volume < 0
        or item.high < max(item.open, item.close)
        or item.low > min(item.open, item.close)
        for item in ordered
    ):
        raise IncompleteCandleHistoryError("Stock OHLCV values are invalid.")
    required = required_candle_sessions(config)
    if len(ordered) < required:
        raise IncompleteCandleHistoryError(
            f"At least {required} complete candles are required."
        )
    result = _analyze_latest(
        ordered,
        benchmark_candles=benchmark_candles,
        config=config,
        detect_failure=True,
    )
    evidence_timeframes = {item.timeframe for item in result.chart_evidence}
    if len(evidence_timeframes) < 2:
        return result

    selected_timeframe = result.consolidation_timeframe
    chart_evidence: list[TechnicalChartEvidence] = []
    for evidence in result.chart_evidence:
        if evidence.timeframe == selected_timeframe:
            chart_evidence.append(replace(evidence, status=result.status))
            continue
        scoped = _analyze_latest(
            ordered,
            benchmark_candles=benchmark_candles,
            config=config,
            detect_failure=True,
            timeframe_filter=evidence.timeframe,
        )
        chart_evidence.extend(
            item
            for item in scoped.chart_evidence
            if item.timeframe == evidence.timeframe
        )
    return replace(
        result,
        chart_evidence=tuple(
            sorted(chart_evidence, key=lambda item: item.timeframe)
        ),
    )
