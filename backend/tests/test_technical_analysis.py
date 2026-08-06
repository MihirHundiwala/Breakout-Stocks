from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.technical_analysis import (
    IncompleteCandleHistoryError,
    TechnicalAnalysisConfig,
    TechnicalChartEvidence,
    _base_regime_drift,
    _breakout_holding_active,
    _breakout_retest_eligible,
    _choose_consolidation,
    _completed_weekly_candles,
    _confirmed_pivot_highs,
    _contraction_measurement,
    _extend_chart_evidence_to_analysis_date,
    _is_approaching_resistance,
    _resistance_clusters,
    _resistance_zone,
    _true_ranges,
    analyze_technical_setup,
)
from app.models import TechnicalStatus
from app.providers.contracts import DailyCandle


START = date(2024, 1, 1)
ZERO = Decimal("0")


def candle(
    index: int,
    close: Decimal,
    *,
    open_price: Decimal | None = None,
    high: Decimal | None = None,
    low: Decimal | None = None,
    volume: int = 1000,
) -> DailyCandle:
    trading_date = START + timedelta(days=index)
    return DailyCandle(
        trading_date=trading_date,
        timestamp=datetime.combine(trading_date, datetime.min.time(), tzinfo=UTC),
        open=open_price if open_price is not None else close - Decimal("0.4"),
        high=high if high is not None else close + Decimal("1"),
        low=low if low is not None else close - Decimal("1"),
        close=close,
        volume=volume,
        open_interest=0,
    )


def setup_candles(
    *,
    current_close: Decimal = Decimal("198"),
    current_high: Decimal | None = None,
    current_low: Decimal | None = None,
    current_volume: int = 500,
    touch_offsets: tuple[int, ...] = (5, 15, 25, 35),
    touch_prices: tuple[Decimal, ...] | None = None,
) -> list[DailyCandle]:
    candles: list[DailyCandle] = []
    for index in range(220):
        close = Decimal("80") + Decimal(index) * Decimal("0.50")
        candles.append(candle(index, close, volume=1000))

    for offset in range(40):
        close = Decimal("190") + Decimal(offset) * Decimal("0.12")
        candles.append(
            candle(
                220 + offset,
                close,
                high=close + Decimal("0.8"),
                low=close - Decimal("1.2"),
                volume=400 if offset >= 30 else 900,
            )
        )

    prices = touch_prices or tuple(Decimal("200") for _ in touch_offsets)
    for offset, price in zip(touch_offsets, prices, strict=True):
        index = 220 + offset
        candles[index] = candle(
            index,
            Decimal("196"),
            open_price=Decimal("195"),
            high=price,
            low=Decimal("194"),
            volume=800,
        )

    candles.append(
        candle(
            260,
            current_close,
            open_price=current_close - Decimal("0.8"),
            high=current_high if current_high is not None else current_close + Decimal("0.4"),
            low=current_low if current_low is not None else current_close - Decimal("1.6"),
            volume=current_volume,
        )
    )
    return candles


def early_recovery_candles(
    *,
    current_volume: int = 2200,
) -> list[DailyCandle]:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=current_volume,
    )
    # A prior high-price regime keeps SMA200 above SMA150 and gently declining,
    # while the recent 50-session trend and breakout are already constructive.
    for index in range(41, 101):
        candles[index] = candle(
            index,
            Decimal("230"),
            open_price=Decimal("229.5"),
            high=Decimal("231"),
            low=Decimal("229"),
            volume=1000,
        )
    return candles


def long_base_candles() -> list[DailyCandle]:
    candles: list[DailyCandle] = []
    for index in range(140):
        close = Decimal("80") + Decimal(index) * Decimal("0.75")
        candles.append(candle(index, close, volume=1000))

    for offset in range(120):
        close = Decimal("190") + Decimal(offset) * Decimal("0.05")
        candles.append(
            candle(
                140 + offset,
                close,
                high=close + Decimal("0.8"),
                low=close - Decimal("1.2"),
                volume=400 if offset >= 110 else 900,
            )
        )

    for offset in (10, 70, 110):
        index = 140 + offset
        candles[index] = candle(
            index,
            Decimal("196"),
            open_price=Decimal("195"),
            high=Decimal("200"),
            low=Decimal("194"),
            volume=800,
        )

    candles.append(
        candle(
            260,
            Decimal("198"),
            high=Decimal("198.4"),
            low=Decimal("196.4"),
            volume=500,
        )
    )
    return candles


def benchmark_candles(stock: list[DailyCandle]) -> list[DailyCandle]:
    return [
        candle(
            index,
            Decimal("100") + Decimal(index) * Decimal("0.08"),
            open_price=Decimal("100") + Decimal(index) * Decimal("0.08"),
            high=Decimal("100.1") + Decimal(index) * Decimal("0.08"),
            low=Decimal("99.9") + Decimal(index) * Decimal("0.08"),
        )
        for index in range(len(stock))
    ]


def analyze(
    candles: list[DailyCandle],
    *,
    benchmark: list[DailyCandle] | None = None,
    target_index: int = -1,
    include_default_benchmark: bool = True,
    config: TechnicalAnalysisConfig = TechnicalAnalysisConfig(),
):
    target = candles[target_index].trading_date
    return analyze_technical_setup(
        candles,
        benchmark_candles=(
            benchmark
            if benchmark is not None
            else (benchmark_candles(candles) if include_default_benchmark else None)
        ),
        target_session=target,
        expected_sessions=[item.trading_date for item in candles if item.trading_date <= target],
        config=config,
    )


def test_default_v21_thresholds_are_duration_sensitive() -> None:
    config = TechnicalAnalysisConfig()

    assert config.consolidation_windows == tuple(range(20, 121))
    assert config.minimum_base_depth == Decimal("0")
    assert config.maximum_base_depth == Decimal("0.24")
    assert config.maximum_body_base_depth == Decimal("0.18")
    assert config.base_depth_limits(20) == (
        Decimal("0.12"),
        Decimal("0.16"),
    )
    assert config.base_depth_limits(39) == (
        Decimal("0.12"),
        Decimal("0.16"),
    )
    assert config.base_depth_limits(40) == (
        Decimal("0.15"),
        Decimal("0.20"),
    )
    assert config.base_depth_limits(79) == (
        Decimal("0.15"),
        Decimal("0.20"),
    )
    assert config.base_depth_limits(80) == (
        Decimal("0.18"),
        Decimal("0.24"),
    )
    assert config.base_depth_limits(120) == (
        Decimal("0.18"),
        Decimal("0.24"),
    )
    assert config.base_range_trim_fraction == Decimal("0.05")
    assert config.maximum_26_week_high_distance == Decimal("0.10")
    assert config.maximum_consolidating_distance == Decimal("0.05")
    assert config.minimum_base_position == Decimal("0.75")
    assert config.approach_lookback_sessions == 5
    assert config.maximum_base_regime_drift == Decimal("0.08")
    assert config.minimum_contraction_checks == 1
    assert config.resistance_atr_tolerance == Decimal("0.36")
    assert config.volume_contraction_weight == Decimal("0")
    assert config.minimum_breakout_volume_ratio == Decimal("1.40")
    assert config.breakout_confirmation_percent == Decimal("0.001")
    assert config.breakout_confirmation_atr == Decimal("0.10")
    assert config.minimum_early_recovery_volume_ratio == Decimal("2.00")
    assert config.minimum_early_recovery_close_location == Decimal("0.75")
    assert config.maximum_early_recovery_extension_atr == Decimal("2.50")
    assert config.maximum_early_recovery_sma150_gap == Decimal("0.08")
    assert config.maximum_early_recovery_sma200_decline == Decimal("0.02")
    assert config.weekly_consolidation_windows == tuple(range(26, 105))
    assert config.weekly_base_depth_limits(26) == (
        Decimal("0.25"),
        Decimal("0.30"),
    )
    assert config.weekly_base_depth_limits(104) == (
        Decimal("0.32"),
        Decimal("0.38"),
    )
    assert config.weekly_minimum_resistance_touches == 3
    assert config.algorithm_version == "technical-v21"
    assert config.weekly_contraction_recent_periods == 5
    assert config.weekly_contraction_reference_periods == 20
    assert config.weekly_maximum_ma_spread == Decimal("0.08")
    assert config.failure_window_sessions == 5
    assert config.weekly_breakout_holding_weeks == 3
    assert config.retest_window_sessions == 20
    assert config.weekly_retest_window_weeks == 8
    assert config.maximum_holding_extension_atr == Decimal("3")
    assert config.maximum_holding_extension_pct == Decimal("0.15")
    assert config.maximum_recent_resistance_extension_atr == Decimal("0.35")
    assert TechnicalAnalysisConfig(consolidation_windows=(12, 24)).maximum_base_sessions == 24


def test_weekly_aggregation_excludes_the_unfinished_signal_week() -> None:
    daily = [
        candle(0, Decimal("100"), open_price=Decimal("99"), high=Decimal("102"), low=Decimal("98"), volume=100),
        candle(1, Decimal("103"), open_price=Decimal("100"), high=Decimal("104"), low=Decimal("99"), volume=150),
        candle(7, Decimal("105"), open_price=Decimal("104"), high=Decimal("107"), low=Decimal("103"), volume=200),
        candle(8, Decimal("106"), open_price=Decimal("105"), high=Decimal("108"), low=Decimal("104"), volume=250),
        candle(14, Decimal("109"), open_price=Decimal("107"), high=Decimal("110"), low=Decimal("106"), volume=300),
    ]

    completed = _completed_weekly_candles(
        daily,
        signal_date=daily[-1].trading_date,
    )
    chart_weeks = _completed_weekly_candles(
        daily,
        signal_date=daily[-1].trading_date,
        include_signal_week=True,
    )

    assert len(completed) == 2
    assert len(chart_weeks) == 3
    assert chart_weeks[-1].trading_date == daily[-1].trading_date
    assert completed[0].open == Decimal("99")
    assert completed[0].high == Decimal("104")
    assert completed[0].low == Decimal("98")
    assert completed[0].close == Decimal("103")
    assert completed[0].volume == 250


def test_weekly_lifecycle_chart_includes_the_latest_partial_week() -> None:
    daily = [
        candle(index, Decimal("100") + index, volume=100 + index)
        for index in range(16)
    ]
    initial_weeks = _completed_weekly_candles(
        daily[:8],
        signal_date=daily[7].trading_date,
        include_signal_week=True,
    )
    evidence = TechnicalChartEvidence(
        timeframe="WEEKLY",
        period_count=26,
        status=TechnicalStatus.BREAKOUT,
        resistance_price=Decimal("105"),
        resistance_zone_lower=Decimal("104"),
        resistance_zone_upper=Decimal("106"),
        resistance_touch_dates=(),
        candles=initial_weeks,
    )

    extended = _extend_chart_evidence_to_analysis_date(
        evidence,
        ordered=daily,
        status=TechnicalStatus.BREAKOUT_HOLDING,
    )

    assert extended.period_count == evidence.period_count
    assert extended.status == TechnicalStatus.BREAKOUT_HOLDING
    assert extended.candles[-1].trading_date == daily[-1].trading_date
    assert extended.candles[-1].close == daily[-1].close


def test_long_weekly_shelf_uses_two_separated_wick_rejections() -> None:
    weeks = [
        candle(
            index * 7,
            Decimal("185") + Decimal(index % 5),
            open_price=Decimal("184") + Decimal(index % 5),
            high=(
                Decimal("200")
                if index in {5, 45}
                else Decimal("190") + Decimal(index) / Decimal("100")
            ),
            low=Decimal("174"),
            volume=1000,
        )
        for index in range(52)
    ]
    config = TechnicalAnalysisConfig()
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
        resistance_touch_full_score_count=4,
        resistance_separation_full_score_sessions=4,
    )

    search = _choose_consolidation(
        weeks,
        current_close=Decimal("196"),
        current_date=weeks[-1].trading_date + timedelta(days=7),
        atr14=Decimal("2"),
        contraction=_contraction_measurement(
            weeks,
            scale_close=weeks[-1].close,
            config=config,
            timeframe="WEEKLY",
        ),
        config=weekly_config,
        timeframe="WEEKLY",
        require_launch_area=True,
    )

    assert search.candidate is not None
    assert search.candidate.timeframe == "WEEKLY"
    assert search.candidate.window >= 40
    assert len(search.candidate.resistance.touch_dates) == 2


def test_confirmed_stage2_stock_is_consolidating() -> None:
    result = analyze(setup_candles())

    assert result.status == TechnicalStatus.CONSOLIDATING
    assert result.close_price > result.sma50 > result.sma150 > result.sma200
    assert result.stage2_score > Decimal("0.50")
    assert result.high_52_week >= result.close_price
    assert result.low_52_week > 0


def test_one_contraction_confirmation_keeps_a_structurally_tight_base() -> None:
    result = analyze(
        setup_candles(),
        config=TechnicalAnalysisConfig(
            maximum_atr_contraction_ratio=Decimal("0.0001"),
            maximum_return_volatility_ratio=Decimal("0.0001"),
            maximum_daily_range_ratio=Decimal("0.0001"),
        ),
    )

    assert result.status == TechnicalStatus.CONSOLIDATING
    assert result.tightness_pass_count == 1


def test_stage2_setup_far_below_resistance_is_not_actionable() -> None:
    result = analyze(
        setup_candles(
            touch_prices=(
                Decimal("230"),
                Decimal("230"),
                Decimal("230"),
                Decimal("230"),
            )
        )
    )

    assert result.status == TechnicalStatus.NO_SETUP
    assert result.distance_to_resistance_pct is not None
    assert result.distance_to_resistance_pct > Decimal("0.05")
    assert "TOO_FAR_FROM_26_WEEK_HIGH" in result.rejection_reasons


def test_invalid_downtrend_is_hard_rejected() -> None:
    candles = setup_candles()
    for index, item in enumerate(candles):
        close = Decimal("300") - Decimal(index) * Decimal("0.50")
        candles[index] = candle(index, close)

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "NOT_CONFIRMED_STAGE2" in result.rejection_reasons


def test_tight_consolidation_reports_shifted_base_metrics() -> None:
    result = analyze(setup_candles())

    assert result.consolidation_window is not None
    assert 20 <= result.consolidation_window <= 120
    assert result.base_depth_pct is not None
    assert Decimal("0") < result.base_depth_pct
    assert result.base_depth_pct <= TechnicalAnalysisConfig().base_depth_limits(
        result.consolidation_window
    )[0]
    assert result.base_position is not None and result.base_position >= Decimal("0.75")
    assert result.resistance_price is not None
    assert result.resistance_price == Decimal("198")
    assert result.resistance_zone_lower < result.resistance_price
    assert result.resistance_zone_upper > result.resistance_price
    assert result.volume_dryup_ratio is None
    assert result.volume_contraction_score == Decimal("0")
    assert result.tightness_pass_count >= 2


def test_one_confirmed_wick_above_body_shelf_does_not_extend_breakout_ceiling() -> None:
    candles = setup_candles(
        current_close=Decimal("200.6"),
        current_high=Decimal("201.4"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    # One candle's body tests the established shelf while its wick rejects a
    # higher price. The isolated wick must not move a repeatedly tested zone.
    candles[233] = candle(
        233,
        Decimal("195.2"),
        open_price=Decimal("194.8"),
        high=Decimal("202"),
        low=Decimal("194"),
        volume=800,
    )

    result = analyze(candles)

    assert result.resistance_zone_upper == Decimal("200")
    assert result.close_price > result.resistance_zone_upper
    assert result.status == TechnicalStatus.BREAKOUT


def test_weekly_touch_deduplication_preserves_highest_coherent_wick() -> None:
    weeks = [
        candle(
            index,
            Decimal("95") + Decimal(index) / Decimal("10"),
            high=Decimal("97") + Decimal(index) / Decimal("10"),
            low=Decimal("93"),
        )
        for index in range(10)
    ]
    weeks[2] = candle(2, Decimal("96"), high=Decimal("100"), low=Decimal("94"))
    weeks[4] = candle(4, Decimal("96"), high=Decimal("101"), low=Decimal("94"))
    weeks[7] = candle(7, Decimal("96"), high=Decimal("100"), low=Decimal("94"))
    config = replace(
        TechnicalAnalysisConfig(),
        pivot_left_sessions=1,
        pivot_right_sessions=1,
        minimum_resistance_touches=2,
        minimum_touch_separation_sessions=3,
        resistance_pivots_use_wicks=True,
    )

    clusters = _resistance_clusters(
        weeks,
        atr14=Decimal("5"),
        config=config,
    )

    assert clusters
    assert max(item.rejection_ceiling for item in clusters) == Decimal("100.5")
    assert any(len(item.touch_indices) == 2 for item in clusters)


def test_weekly_contraction_uses_completed_week_ranges() -> None:
    weeks = [
        candle(
            index,
            Decimal("100") + Decimal(index % 3),
            high=(
                Decimal("108")
                if index < 25
                else Decimal("104")
            ),
            low=(
                Decimal("94")
                if index < 25
                else Decimal("98")
            ),
        )
        for index in range(30)
    ]

    measurement = _contraction_measurement(
        weeks,
        scale_close=weeks[-1].close,
        config=TechnicalAnalysisConfig(),
        timeframe="WEEKLY",
    )

    assert measurement.atr_ratio is not None
    assert measurement.atr_ratio < Decimal("0.90")
    assert measurement.range_ratio is not None
    assert measurement.range_ratio < Decimal("0.90")
    assert measurement.pass_count >= 2


def test_consolidation_can_be_selected_beyond_forty_sessions() -> None:
    candles = long_base_candles()
    benchmark = benchmark_candles(candles)
    for index in range(140, len(benchmark)):
        close = Decimal("112") - Decimal(index - 140) * Decimal("0.03")
        benchmark[index] = candle(index, close)
    result = analyze(candles, benchmark=benchmark)

    assert result.status == TechnicalStatus.CONSOLIDATING
    assert result.consolidation_window is not None
    assert 40 < result.consolidation_window <= 120
    assert result.resistance_touch_count >= 2


def test_longest_valid_window_is_selected_within_the_same_resistance_shelf() -> None:
    result = analyze(
        setup_candles(),
        config=TechnicalAnalysisConfig(consolidation_windows=(20, 40)),
    )

    assert result.status == TechnicalStatus.CONSOLIDATING
    assert result.consolidation_window == 40


def test_directional_markup_is_not_one_coherent_long_base() -> None:
    gently_rising = [
        candle(index, Decimal("100") + Decimal(index) * Decimal("0.15"))
        for index in range(40)
    ]
    directional_markup = [
        candle(index, Decimal("100") + Decimal(index) * Decimal("0.50"))
        for index in range(40)
    ]

    assert _base_regime_drift(
        gently_rising,
        base_high=max(item.high for item in gently_rising),
    ) <= Decimal("0.08")
    assert _base_regime_drift(
        directional_markup,
        base_high=max(item.high for item in directional_markup),
    ) > Decimal("0.08")


def test_loose_consolidation_is_rejected() -> None:
    candles = setup_candles()
    for index in range(220, 260):
        item = candles[index]
        wide_high = index % 5 == 0
        wide_low = index % 5 == 2
        close = (
            Decimal("206")
            if wide_high
            else Decimal("170") if wide_low else item.close
        )
        candles[index] = candle(
            index,
            close,
            open_price=close - Decimal("1"),
            high=Decimal("210") if wide_high else close + Decimal("1"),
            low=Decimal("160") if wide_low else close - Decimal("1"),
            volume=item.volume,
        )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "NO_TIGHT_RESISTANCE_CONSOLIDATION" in result.rejection_reasons


def test_one_extreme_wick_does_not_define_the_base() -> None:
    candles = setup_candles()
    item = candles[240]
    candles[240] = candle(
        240,
        item.close,
        open_price=item.open,
        high=Decimal("240"),
        low=Decimal("170"),
        volume=item.volume,
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.CONSOLIDATING
    assert result.base_depth_pct is not None
    assert result.base_depth_pct <= TechnicalAnalysisConfig().base_depth_limits(
        result.consolidation_window
    )[0]


def test_two_separated_pivots_form_resistance_cluster() -> None:
    candles = setup_candles(touch_offsets=(15, 35))
    result = analyze(candles)

    assert result.resistance_price == Decimal("198")
    assert result.resistance_touch_count == 2
    assert result.resistance_touch_dates == (
        candles[235].trading_date,
        candles[255].trading_date,
    )


def test_extreme_wick_does_not_hide_the_next_body_high_pivot() -> None:
    base = [candle(index, Decimal("190")) for index in range(14)]
    base[5] = candle(
        5,
        Decimal("195"),
        open_price=Decimal("194"),
        high=Decimal("210"),
        low=Decimal("193"),
    )
    base[6] = candle(
        6,
        Decimal("199"),
        open_price=Decimal("198"),
        high=Decimal("200"),
        low=Decimal("197"),
    )

    pivots = _confirmed_pivot_highs(base, left_sessions=1, right_sessions=1)

    assert 6 in pivots


def test_adjacent_pivot_candles_are_not_multiple_touches() -> None:
    base = setup_candles(touch_offsets=())[-41:-1]
    for offset in (20, 21):
        index = offset
        base[index] = candle(
            220 + index,
            Decimal("196"),
            high=Decimal("200"),
            low=Decimal("194"),
        )
    pivots = _confirmed_pivot_highs(base, left_sessions=1, right_sessions=1)
    clusters = _resistance_clusters(
        base,
        atr14=Decimal("2"),
        config=TechnicalAnalysisConfig(pivot_left_sessions=1, pivot_right_sessions=1),
    )

    assert len([index for index in pivots if index in (20, 21)]) <= 2
    assert not clusters


def test_resistance_prices_inside_tolerance_are_clustered_by_median() -> None:
    candles = setup_candles(
        touch_prices=(Decimal("199.5"), Decimal("200"), Decimal("200.5"), Decimal("200"))
    )
    result = analyze(candles)

    assert result.resistance_price is not None
    assert Decimal("197.5") <= result.resistance_price <= Decimal("198.5")
    assert result.resistance_touch_count >= 2
    assert result.resistance_dispersion_pct is not None
    assert result.resistance_dispersion_pct <= Decimal("0.01")


def test_refined_cluster_keeps_a_nearby_third_rejection_pivot() -> None:
    closes = (
        Decimal("530"), Decimal("531"), Decimal("532"), Decimal("558.4"),
        Decimal("533"), Decimal("534"), Decimal("535"), Decimal("557.2"),
        Decimal("557.2"), Decimal("536"), Decimal("537"), Decimal("538"),
        Decimal("567"), Decimal("539"), Decimal("540"), Decimal("541"),
    )
    base = [candle(index, close) for index, close in enumerate(closes)]
    base[3] = candle(
        3,
        Decimal("558.4"),
        open_price=Decimal("557"),
        high=Decimal("574.9"),
        low=Decimal("556"),
    )
    for index in (7, 8):
        base[index] = candle(
            index,
            Decimal("557.2"),
            open_price=Decimal("556"),
            high=Decimal("558.45"),
            low=Decimal("555"),
        )
    base[12] = candle(
        12,
        Decimal("567"),
        open_price=Decimal("566"),
        high=Decimal("571.55"),
        low=Decimal("555"),
    )

    clusters = _resistance_clusters(
        base,
        atr14=Decimal("26.107142857"),
        config=TechnicalAnalysisConfig(),
    )

    assert any(
        cluster.touch_dates
        == (base[3].trading_date, base[7].trading_date, base[12].trading_date)
        and cluster.resistance == Decimal("567")
        for cluster in clusters
    )


def test_chart_marks_every_rejection_near_the_resistance_zone() -> None:
    base = [candle(index, Decimal("190")) for index in range(24)]
    for index in (4, 12, 13, 14, 20):
        base[index] = candle(
            index,
            Decimal("196"),
            open_price=Decimal("195"),
            high=Decimal("200"),
            low=Decimal("194"),
        )

    clusters = _resistance_clusters(
        base,
        atr14=Decimal("3"),
        config=TechnicalAnalysisConfig(),
    )
    cluster = max(clusters, key=lambda item: len(item.marker_dates))

    assert len(cluster.touch_indices) >= 2
    assert set(base[index].trading_date for index in (4, 12, 13, 14, 20)).issubset(
        set(cluster.marker_dates)
    )


def test_intervening_accepted_bodies_invalidate_the_lower_resistance_shelf() -> None:
    base = [candle(index, Decimal("190")) for index in range(24)]
    for index in (4, 18):
        base[index] = candle(
            index,
            Decimal("195"),
            open_price=Decimal("196"),
            high=Decimal("200"),
            low=Decimal("193"),
        )
    base[9] = candle(
        9,
        Decimal("204"),
        open_price=Decimal("199"),
        high=Decimal("205"),
        low=Decimal("198"),
    )
    base[10] = candle(
        10,
        Decimal("205"),
        open_price=Decimal("204"),
        high=Decimal("206"),
        low=Decimal("203"),
    )
    base[12] = candle(12, Decimal("190"), high=Decimal("192"), low=Decimal("188"))

    clusters = _resistance_clusters(
        base,
        atr14=Decimal("3"),
        config=TechnicalAnalysisConfig(),
    )

    lower_touch_dates = {base[4].trading_date, base[18].trading_date}
    assert all(
        cluster.preinvalidated
        or not lower_touch_dates.issubset(set(cluster.touch_dates))
        for cluster in clusters
    )


def test_one_outlier_wick_does_not_set_the_breakout_zone_ceiling() -> None:
    base = [candle(index, Decimal("1400")) for index in range(22)]
    touches = (
        (3, Decimal("1439"), Decimal("1440"), Decimal("1518")),
        (9, Decimal("1448"), Decimal("1450"), Decimal("1457")),
        (15, Decimal("1442"), Decimal("1444"), Decimal("1455")),
    )
    for index, open_price, close, high in touches:
        base[index] = candle(
            index,
            close,
            open_price=open_price,
            high=high,
            low=Decimal("1395"),
        )

    clusters = _resistance_clusters(
        base,
        atr14=Decimal("30"),
        config=TechnicalAnalysisConfig(),
    )
    cluster = max(clusters, key=lambda item: len(item.touch_indices))
    _, zone_upper = _resistance_zone(
        cluster,
        atr14=Decimal("30"),
        config=TechnicalAnalysisConfig(),
    )

    assert cluster.resistance == Decimal("1450.5")
    assert zone_upper < Decimal("1500")


def test_strong_volume_breakout_is_confirmed() -> None:
    result = analyze(
        setup_candles(
            current_close=Decimal("201.2"),
            current_high=Decimal("201.5"),
            current_low=Decimal("199.5"),
            current_volume=2200,
        )
    )

    assert result.status == TechnicalStatus.BREAKOUT
    assert result.breakout_volume_ratio is not None
    assert result.breakout_volume_ratio >= Decimal("1.4")
    assert result.close_location_value >= Decimal("0.70")
    assert result.breakout_extension_atr is not None
    assert result.breakout_extension_atr <= Decimal("1.5")
    assert result.chart_evidence
    assert result.chart_evidence[0].candles[-1].trading_date == result.analysis_date


def test_early_recovery_breakout_is_separate_from_confirmed_stage2() -> None:
    result = analyze(early_recovery_candles())

    assert result.status == TechnicalStatus.EARLY_RECOVERY_BREAKOUT
    assert result.close_price > result.sma50 > result.sma150
    assert result.close_price > result.sma200 > result.sma150
    assert result.breakout_volume_ratio is not None
    assert result.breakout_volume_ratio >= Decimal("2")
    assert result.rejection_reasons == ()


def test_early_recovery_requires_stronger_volume_confirmation() -> None:
    result = analyze(early_recovery_candles(current_volume=800))

    assert result.status == TechnicalStatus.NO_SETUP
    assert "NOT_CONFIRMED_STAGE2" in result.rejection_reasons


def test_early_recovery_rejects_a_sharply_falling_sma200() -> None:
    result = analyze(
        early_recovery_candles(),
        config=TechnicalAnalysisConfig(
            maximum_early_recovery_sma200_decline=Decimal("0"),
        ),
    )

    assert result.status == TechnicalStatus.NO_SETUP
    assert "NOT_CONFIRMED_STAGE2" in result.rejection_reasons


def test_weak_volume_breakout_is_not_confirmed() -> None:
    result = analyze(
        setup_candles(
            current_close=Decimal("201.2"),
            current_high=Decimal("201.5"),
            current_low=Decimal("199.5"),
            current_volume=300,
        )
    )

    assert result.status == TechnicalStatus.WEAK_BREAKOUT
    assert "WEAK_BREAKOUT_VOLUME" in result.rejection_reasons
    assert result.chart_evidence
    assert result.chart_evidence[0].candles[-1].trading_date == result.analysis_date


def test_base_selection_is_independent_of_base_volume_pattern() -> None:
    ordinary_volume = setup_candles()
    distribution_volume = [
        replace(item, volume=8000) if index in (226, 236, 246, 256) else item
        for index, item in enumerate(ordinary_volume)
    ]

    ordinary_result = analyze(ordinary_volume)
    distribution_result = analyze(distribution_volume)

    assert (
        distribution_result.status
        == ordinary_result.status
        == TechnicalStatus.CONSOLIDATING
    )
    assert distribution_result.consolidation_window == ordinary_result.consolidation_window
    assert distribution_result.resistance_price == ordinary_result.resistance_price
    assert distribution_result.resistance_touch_dates == ordinary_result.resistance_touch_dates
    assert distribution_result.volume_contraction_score == ordinary_result.volume_contraction_score == ZERO
    assert distribution_result.setup_score == ordinary_result.setup_score


def test_high_volume_breakout_with_long_upper_wick_is_strong() -> None:
    result = analyze(
        setup_candles(
            current_close=Decimal("201.2"),
            current_high=Decimal("205"),
            current_low=Decimal("199.5"),
            current_volume=2200,
        )
    )

    assert result.status == TechnicalStatus.BREAKOUT
    assert "WEAK_BREAKOUT_CLOSE" not in result.rejection_reasons


def test_high_volume_overextended_breakout_is_strong() -> None:
    result = analyze(
        setup_candles(
            current_close=Decimal("205"),
            current_high=Decimal("205.2"),
            current_low=Decimal("203.5"),
            current_volume=2200,
        )
    )

    assert result.status == TechnicalStatus.BREAKOUT
    assert "BREAKOUT_OVEREXTENDED" not in result.rejection_reasons


def test_breakout_candle_cannot_create_ordinary_stage2_confirmation() -> None:
    candles = setup_candles(
        current_close=Decimal("205"),
        current_high=Decimal("205.2"),
        current_low=Decimal("203.5"),
        current_volume=2200,
    )
    candles[-2] = candle(
        259,
        Decimal("187"),
        high=Decimal("195"),
        low=Decimal("186"),
        volume=400,
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.EARLY_RECOVERY_BREAKOUT
    assert result.status not in {
        TechnicalStatus.BREAKOUT,
        TechnicalStatus.WEAK_BREAKOUT,
    }


def test_decisive_close_after_marginal_probe_is_breakout_not_retest() -> None:
    candles = setup_candles(
        current_close=Decimal("200.05"),
        current_high=Decimal("201"),
        current_low=Decimal("198"),
        current_volume=2200,
    )

    marginal_probe = analyze(candles)
    assert marginal_probe.status == TechnicalStatus.CONSOLIDATING

    candles.append(
        candle(
            261,
            Decimal("202"),
            high=Decimal("203"),
            low=Decimal("199"),
            volume=2200,
        )
    )
    decisive_close = analyze(candles)

    assert decisive_close.status == TechnicalStatus.BREAKOUT
    assert decisive_close.resistance_price == Decimal("198")


def test_retest_is_detected_when_prior_breakout_zone_holds() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    candles.append(
        candle(
            261,
            Decimal("200.2"),
            high=Decimal("201"),
            low=Decimal("196"),
            volume=900,
        )
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.RETEST
    assert result.resistance_price == Decimal("198")
    assert result.consolidation_start is not None
    assert result.chart_evidence
    assert result.chart_evidence[0].status == TechnicalStatus.RETEST
    assert result.chart_evidence[0].candles[-1].trading_date == result.analysis_date


def test_zone_touch_retest_survives_temporary_current_relative_strength_weakness() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    candles.append(
        candle(
            261,
            Decimal("200.2"),
            high=Decimal("202"),
            low=Decimal("199.5"),
            volume=900,
        )
    )
    benchmark = benchmark_candles(candles)
    benchmark[-1] = candle(
        261,
        Decimal("150"),
        open_price=Decimal("149"),
        high=Decimal("151"),
        low=Decimal("148"),
    )

    result = analyze(candles, benchmark=benchmark)

    assert result.relative_strength_score == ZERO
    assert result.status == TechnicalStatus.RETEST
    assert result.rejection_reasons == ()


def test_early_recovery_breakout_can_form_a_retest() -> None:
    candles = early_recovery_candles()
    candles.append(
        candle(
            261,
            Decimal("198.5"),
            high=Decimal("200.5"),
            low=Decimal("196.5"),
            volume=900,
        )
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.RETEST
    assert result.resistance_price is not None


def test_recent_breakout_holding_above_the_zone_remains_visible() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    candles.append(
        candle(
            261,
            Decimal("202"),
            high=Decimal("203"),
            low=Decimal("201.2"),
            volume=900,
        )
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.BREAKOUT_HOLDING
    assert result.resistance_price == Decimal("198")
    assert result.rejection_reasons == ()
    assert result.chart_evidence
    assert result.chart_evidence[0].status == TechnicalStatus.BREAKOUT_HOLDING
    assert result.chart_evidence[0].candles[-1].trading_date == result.analysis_date


def test_same_shelf_cannot_emit_a_second_breakout_during_holding() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    candles.append(
        candle(
            261,
            Decimal("202"),
            high=Decimal("203"),
            low=Decimal("201.2"),
            volume=2200,
        )
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.BREAKOUT_HOLDING
    assert result.rejection_reasons == ()


def test_breakout_holding_windows_are_timeframe_specific() -> None:
    config = TechnicalAnalysisConfig()
    breakout_date = date(2026, 7, 6)

    assert _breakout_holding_active(
        timeframe="DAILY",
        breakout_date=breakout_date,
        current_date=date(2026, 7, 13),
        sessions_elapsed=5,
        config=config,
    )
    assert not _breakout_holding_active(
        timeframe="DAILY",
        breakout_date=breakout_date,
        current_date=date(2026, 7, 14),
        sessions_elapsed=6,
        config=config,
    )
    assert _breakout_holding_active(
        timeframe="WEEKLY",
        breakout_date=breakout_date,
        current_date=date(2026, 7, 27),
        sessions_elapsed=15,
        config=config,
    )
    assert not _breakout_holding_active(
        timeframe="WEEKLY",
        breakout_date=breakout_date,
        current_date=date(2026, 8, 3),
        sessions_elapsed=20,
        config=config,
    )

    assert _breakout_retest_eligible(
        timeframe="DAILY",
        breakout_date=breakout_date,
        current_date=date(2026, 8, 3),
        sessions_elapsed=20,
        config=config,
    )
    assert not _breakout_retest_eligible(
        timeframe="DAILY",
        breakout_date=breakout_date,
        current_date=date(2026, 8, 4),
        sessions_elapsed=21,
        config=config,
    )
    assert _breakout_retest_eligible(
        timeframe="WEEKLY",
        breakout_date=breakout_date,
        current_date=date(2026, 8, 31),
        sessions_elapsed=40,
        config=config,
    )
    assert not _breakout_retest_eligible(
        timeframe="WEEKLY",
        breakout_date=breakout_date,
        current_date=date(2026, 9, 7),
        sessions_elapsed=45,
        config=config,
    )


def test_breakout_holding_expires_after_five_sessions() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    for index in range(261, 267):
        candles.append(
            candle(
                index,
                Decimal("202"),
                high=Decimal("203"),
                low=Decimal("201.2"),
                volume=900,
            )
        )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP


def test_retest_can_reappear_after_holding_expires_but_before_level_expires() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    for index in range(261, 270):
        candles.append(
            candle(index, Decimal("204"), high=Decimal("205"), low=Decimal("202"), volume=900)
        )
    candles.append(
        candle(270, Decimal("200.2"), high=Decimal("202"), low=Decimal("198"), volume=900)
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.RETEST


def test_retest_level_expires_after_twenty_daily_sessions() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    for index in range(261, 282):
        candles.append(
            candle(index, Decimal("204"), high=Decimal("205"), low=Decimal("202"), volume=900)
        )
    candles.append(
        candle(282, Decimal("200.2"), high=Decimal("202"), low=Decimal("198"), volume=900)
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP


def test_overextended_breakout_holding_is_retired() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    candles.append(
        candle(261, Decimal("235"), high=Decimal("237"), low=Decimal("232"), volume=900)
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP


def test_recent_marginal_probe_extends_live_shelf_instead_of_becoming_retest() -> None:
    candles = setup_candles(
        current_close=Decimal("200.6"),
        current_high=Decimal("201.4"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    candles.append(
        candle(
            261,
            Decimal("200.7"),
            open_price=Decimal("200.4"),
            high=Decimal("201.5"),
            low=Decimal("199.8"),
            volume=900,
        )
    )
    candles.append(
        candle(
            262,
            Decimal("199.5"),
            open_price=Decimal("201.4"),
            high=Decimal("202.2"),
            low=Decimal("198.5"),
            volume=900,
        )
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.CONSOLIDATING
    assert result.resistance_price is not None
    assert result.resistance_price >= Decimal("200.6")


def test_failed_breakout_support_becomes_no_setup() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    candles.append(
        candle(
            261,
            Decimal("195.5"),
            high=Decimal("197"),
            low=Decimal("194.5"),
            volume=1400,
        )
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "BREAKOUT_SUPPORT_FAILED" in result.rejection_reasons


def test_twice_accepted_resistance_is_not_reused_after_recent_failure() -> None:
    candles = setup_candles(
        current_close=Decimal("195"),
        current_high=Decimal("196"),
        current_low=Decimal("193.5"),
        touch_offsets=(5, 15),
    )
    for offset in (35, 36):
        index = 220 + offset
        candles[index] = candle(
            index,
            Decimal("201"),
            open_price=Decimal("200.5"),
            high=Decimal("202"),
            low=Decimal("199.5"),
            volume=500,
        )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "BREAKOUT_SUPPORT_FAILED" in result.rejection_reasons


@pytest.mark.parametrize(
    ("current_close", "current_high", "current_low", "current_volume"),
    (
        (Decimal("198"), Decimal("198.4"), Decimal("196.4"), 500),
        (Decimal("201.2"), Decimal("201.5"), Decimal("199.5"), 2200),
        (Decimal("201.2"), Decimal("205"), Decimal("199.5"), 300),
    ),
)
def test_single_close_failed_breakout_retires_shelf_for_every_primary_status(
    current_close: Decimal,
    current_high: Decimal,
    current_low: Decimal,
    current_volume: int,
) -> None:
    candles = setup_candles(
        current_close=current_close,
        current_high=current_high,
        current_low=current_low,
        current_volume=current_volume,
        touch_offsets=(5, 15, 35),
    )
    candles[245] = candle(
        245,
        Decimal("201"),
        open_price=Decimal("199.5"),
        high=Decimal("203"),
        low=Decimal("199"),
        volume=2200,
    )
    candles[247] = candle(
        247,
        Decimal("194.5"),
        open_price=Decimal("197"),
        high=Decimal("197.5"),
        low=Decimal("194"),
        volume=1600,
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "BREAKOUT_SUPPORT_FAILED" in result.rejection_reasons


def test_single_close_failed_breakout_also_blocks_early_recovery() -> None:
    candles = early_recovery_candles()
    candles[245] = candle(
        245,
        Decimal("201"),
        open_price=Decimal("199.5"),
        high=Decimal("203"),
        low=Decimal("199"),
        volume=2200,
    )
    candles[247] = candle(
        247,
        Decimal("194.5"),
        open_price=Decimal("197"),
        high=Decimal("197.5"),
        low=Decimal("194"),
        volume=1600,
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "BREAKOUT_SUPPORT_FAILED" in result.rejection_reasons


@pytest.mark.parametrize(
    ("next_close", "next_high", "next_low"),
    (
        (Decimal("202"), Decimal("203"), Decimal("201.2")),
        (Decimal("198.5"), Decimal("200.5"), Decimal("196.5")),
    ),
)
def test_invalidated_shelf_cannot_become_holding_or_retest(
    next_close: Decimal,
    next_high: Decimal,
    next_low: Decimal,
) -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("201.5"),
        current_low=Decimal("199.5"),
        current_volume=2200,
        touch_offsets=(5, 15, 35),
    )
    candles[245] = candle(
        245,
        Decimal("201"),
        open_price=Decimal("199.5"),
        high=Decimal("203"),
        low=Decimal("199"),
        volume=2200,
    )
    candles[247] = candle(
        247,
        Decimal("194.5"),
        open_price=Decimal("197"),
        high=Decimal("197.5"),
        low=Decimal("194"),
        volume=1600,
    )
    candles.append(
        candle(
            261,
            next_close,
            high=next_high,
            low=next_low,
            volume=900,
        )
    )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "BREAKOUT_SUPPORT_FAILED" in result.rejection_reasons


def test_approach_requires_non_negative_five_session_progress() -> None:
    candles = setup_candles()

    assert _is_approaching_resistance(
        candles[:-1],
        current_close=Decimal("198"),
        config=TechnicalAnalysisConfig(),
    )
    assert not _is_approaching_resistance(
        candles[:-1],
        current_close=Decimal("195"),
        config=TechnicalAnalysisConfig(),
    )


def test_separate_symbol_calls_do_not_share_rolling_state() -> None:
    strong = analyze(setup_candles())
    falling = setup_candles()
    for index in range(len(falling)):
        close = Decimal("300") - Decimal(index) * Decimal("0.5")
        falling[index] = candle(index, close)

    weak = analyze(falling)
    repeated = analyze(setup_candles())

    assert strong == repeated
    assert weak.status == TechnicalStatus.NO_SETUP


def test_future_candles_do_not_change_point_in_time_result() -> None:
    candles = setup_candles()
    at_t = analyze(candles)
    future = candles + [
        candle(261, Decimal("210"), high=Decimal("215"), low=Decimal("209"), volume=5000),
        candle(262, Decimal("190"), high=Decimal("191"), low=Decimal("185"), volume=6000),
    ]
    with_future_loaded = analyze(future, target_index=260)

    assert with_future_loaded == at_t


def test_breakout_candle_cannot_redefine_its_resistance() -> None:
    candles = setup_candles(
        current_close=Decimal("201.2"),
        current_high=Decimal("230"),
        current_low=Decimal("199.5"),
        current_volume=2200,
    )
    result = analyze(candles)

    assert result.resistance_price == Decimal("198")
    assert result.base_high is not None and result.base_high < Decimal("200")


def test_missing_benchmark_is_an_explicit_no_setup() -> None:
    result = analyze(setup_candles(), include_default_benchmark=False)

    assert result.relative_strength_score is None
    assert result.status == TechnicalStatus.NO_SETUP
    assert "RELATIVE_STRENGTH_UNAVAILABLE" in result.rejection_reasons
    assert ZERO <= result.setup_score <= Decimal("100")


def test_relative_strength_is_scored_when_benchmark_is_available() -> None:
    candles = setup_candles()
    result = analyze(candles, benchmark=benchmark_candles(candles))

    assert result.relative_strength_score is not None
    assert Decimal("0") <= result.relative_strength_score <= Decimal("1")


def test_weak_relative_strength_is_a_hard_gate() -> None:
    candles = setup_candles()
    fast_benchmark = [
        candle(
            index,
            Decimal("100") + Decimal(index) * Decimal("0.8"),
        )
        for index in range(len(candles))
    ]

    result = analyze(candles, benchmark=fast_benchmark)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "WEAK_RELATIVE_STRENGTH" in result.rejection_reasons


def test_stock_more_than_ten_percent_below_26_week_high_is_rejected() -> None:
    candles = setup_candles(current_close=Decimal("198"))
    for offset in range(90, 96):
        spike_index = len(candles) - offset
        spike = candles[spike_index]
        candles[spike_index] = candle(
            spike_index,
            spike.close,
            open_price=spike.open,
            high=Decimal("350"),
            low=spike.low,
            volume=spike.volume,
        )

    result = analyze(candles)

    assert result.status == TechnicalStatus.NO_SETUP
    assert "TOO_FAR_FROM_26_WEEK_HIGH" in result.rejection_reasons


def test_average_traded_value_is_descriptive_not_a_setup_gate() -> None:
    result = analyze(setup_candles())

    assert result.status == TechnicalStatus.CONSOLIDATING
    assert result.average_traded_value_20 > ZERO


def test_zero_range_and_zero_volume_are_handled_safely() -> None:
    candles = setup_candles(current_close=Decimal("198"), current_volume=0)
    candles[-1] = candle(
        260,
        Decimal("198"),
        open_price=Decimal("198"),
        high=Decimal("198"),
        low=Decimal("198"),
        volume=0,
    )
    result = analyze(candles)

    assert result.close_location_value == Decimal("0")
    assert result.breakout_volume_ratio == Decimal("0")


def test_true_range_includes_previous_close_gaps() -> None:
    candles = [
        candle(0, Decimal("100"), high=Decimal("101"), low=Decimal("99")),
        candle(1, Decimal("110"), high=Decimal("111"), low=Decimal("109")),
    ]

    assert _true_ranges(candles) == [Decimal("2"), Decimal("11")]


def test_missing_or_duplicate_sessions_are_rejected() -> None:
    candles = setup_candles()
    with pytest.raises(IncompleteCandleHistoryError, match="Duplicate"):
        analyze(candles + [candles[-1]])

    missing_internal = candles[:100] + candles[101:]
    with pytest.raises(IncompleteCandleHistoryError, match="Expected"):
        analyze_technical_setup(
            missing_internal,
            target_session=candles[-1].trading_date,
            expected_sessions=[item.trading_date for item in candles],
        )
