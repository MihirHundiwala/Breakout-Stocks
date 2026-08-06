"""Replay the current technical algorithm against stored candles, read-only."""

from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import select

from app.db.session import async_session_factory, engine
from app.domain.technical_analysis import (
    TechnicalAnalysisConfig,
    _average,
    _analyze_latest,
    _base_regime_drift,
    _body_high,
    _body_low,
    _contraction_measurement,
    _resistance_clusters,
    _robust_bounds,
    _true_ranges,
    analyze_technical_setup,
)
from app.models import (
    BenchmarkDailyCandle,
    Company,
    DailyCandle,
    Instrument,
    MarketBenchmark,
)
from app.services.live_onboarding import _to_provider_candle


async def audit(symbols: list[str]) -> None:
    async with async_session_factory() as session:
        benchmark_id = await session.scalar(
            select(MarketBenchmark.id).where(MarketBenchmark.code == "NIFTY_500")
        )
        for symbol in symbols:
            identity = (
                await session.execute(
                    select(Instrument.id, Company.name)
                    .join(Company, Company.id == Instrument.company_id)
                    .where(Instrument.trading_symbol == symbol)
                )
            ).one_or_none()
            if identity is None:
                print(json.dumps({"symbol": symbol, "error": "NOT_FOUND"}))
                continue
            instrument_id, company_name = identity
            stock_rows = list(
                await session.scalars(
                    select(DailyCandle)
                    .where(DailyCandle.instrument_id == instrument_id)
                    .order_by(DailyCandle.trading_date)
                )
            )
            if not stock_rows:
                print(json.dumps({"symbol": symbol, "error": "NO_CANDLES"}))
                continue
            target = stock_rows[-1].trading_date
            benchmark_rows = (
                list(
                    await session.scalars(
                        select(BenchmarkDailyCandle)
                        .where(
                            BenchmarkDailyCandle.benchmark_id == benchmark_id,
                            BenchmarkDailyCandle.trading_date <= target,
                        )
                        .order_by(BenchmarkDailyCandle.trading_date)
                    )
                )
                if benchmark_id is not None
                else []
            )
            candles = [_to_provider_candle(item) for item in stock_rows]
            result = analyze_technical_setup(
                candles,
                benchmark_candles=[
                    _to_provider_candle(item) for item in benchmark_rows
                ],
                target_session=target,
                expected_sessions=[item.trading_date for item in stock_rows],
            )
            scoped_results = {
                timeframe: _analyze_latest(
                    candles,
                    benchmark_candles=[
                        _to_provider_candle(item) for item in benchmark_rows
                    ],
                    config=TechnicalAnalysisConfig(),
                    detect_failure=True,
                    timeframe_filter=timeframe,
                )
                for timeframe in ("DAILY", "WEEKLY")
            }
            raw_scoped_results = {
                timeframe: _analyze_latest(
                    candles,
                    benchmark_candles=[
                        _to_provider_candle(item) for item in benchmark_rows
                    ],
                    config=TechnicalAnalysisConfig(),
                    detect_failure=False,
                    timeframe_filter=timeframe,
                )
                for timeframe in ("DAILY", "WEEKLY")
            }
            recent_daily = []
            for sessions_ago in range(min(5, len(candles) - 252), -1, -1):
                subset = candles[:-sessions_ago] if sessions_ago else candles
                scoped = _analyze_latest(
                    subset,
                    benchmark_candles=[
                        _to_provider_candle(item) for item in benchmark_rows
                    ],
                    config=TechnicalAnalysisConfig(),
                    detect_failure=False,
                    timeframe_filter="DAILY",
                )
                recent_daily.append(
                    {
                        "date": scoped.analysis_date.isoformat(),
                        "status": scoped.status.value,
                        "resistance": str(scoped.resistance_price),
                        "zone_upper": str(scoped.resistance_zone_upper),
                    }
                )
            config = TechnicalAnalysisConfig()
            prior = candles[:-1]
            daily_atr = _average(
                _true_ranges(prior)[-config.atr_sessions:]
            )
            daily_contraction = _contraction_measurement(
                prior,
                scale_close=candles[-1].close,
                config=config,
                timeframe="DAILY",
            )
            daily_window_diagnostics = []
            for window in (10, 15, 20, 30):
                if len(prior) < window:
                    continue
                base = prior[-window:]
                base_low, base_high = _robust_bounds(
                    [_body_low(item) for item in base],
                    [_body_high(item) for item in base],
                    trim_fraction=config.base_range_trim_fraction,
                )
                wick_low, wick_high = _robust_bounds(
                    [item.low for item in base],
                    [item.high for item in base],
                    trim_fraction=config.base_range_trim_fraction,
                )
                clusters = _resistance_clusters(
                    base,
                    atr14=daily_atr,
                    config=config,
                    current_close=candles[-1].close,
                )
                maximum_body_depth, maximum_wick_depth = (
                    config.base_depth_limits(max(20, window))
                )
                daily_window_diagnostics.append(
                    {
                        "window": window,
                        "eligible": window in config.consolidation_windows,
                        "body_depth": str((base_high - base_low) / base_high),
                        "maximum_body_depth": str(maximum_body_depth),
                        "wick_depth": str((wick_high - wick_low) / wick_high),
                        "maximum_wick_depth": str(maximum_wick_depth),
                        "regime_drift": str(
                            _base_regime_drift(base, base_high=base_high)
                        ),
                        "maximum_regime_drift": str(
                            config.maximum_base_regime_drift
                        ),
                        "contraction_pass_count": daily_contraction.pass_count,
                        "cluster_count": len(clusters),
                        "clusters": [
                            {
                                "resistance": str(item.resistance),
                                "independent_touches": len(item.touch_indices),
                                "marker_count": len(item.marker_dates),
                            }
                            for item in clusters
                        ],
                    }
                )
            print(
                json.dumps(
                    {
                        "symbol": symbol,
                        "company": company_name,
                        "analysis_date": result.analysis_date.isoformat(),
                        "algorithm_version": result.algorithm_version,
                        "status": result.status.value,
                        "timeframe": result.consolidation_timeframe,
                        "window": result.consolidation_window,
                        "resistance": str(result.resistance_price),
                        "zone_upper": str(result.resistance_zone_upper),
                        "touch_dates": [
                            item.isoformat() for item in result.resistance_touch_dates
                        ],
                        "volume_ratio": str(result.breakout_volume_ratio),
                        "rejection_reasons": list(result.rejection_reasons),
                        "charts": [
                            {
                                "timeframe": item.timeframe,
                                "status": item.status.value,
                                "window": item.period_count,
                                "resistance": str(item.resistance_price),
                                "zone_upper": str(item.resistance_zone_upper),
                                "touch_dates": [
                                    value.isoformat()
                                    for value in item.resistance_touch_dates
                                ],
                            }
                            for item in result.chart_evidence
                        ],
                        "scoped": {
                            timeframe: {
                                "status": scoped.status.value,
                                "window": scoped.consolidation_window,
                                "resistance": str(scoped.resistance_price),
                                "rejection_reasons": list(scoped.rejection_reasons),
                            }
                            for timeframe, scoped in scoped_results.items()
                        },
                        "raw_scoped": {
                            timeframe: {
                                "status": scoped.status.value,
                                "window": scoped.consolidation_window,
                                "resistance": str(scoped.resistance_price),
                                "zone_upper": str(scoped.resistance_zone_upper),
                                "rejection_reasons": list(scoped.rejection_reasons),
                            }
                            for timeframe, scoped in raw_scoped_results.items()
                        },
                        "recent_daily_raw": recent_daily,
                        "daily_window_diagnostics": daily_window_diagnostics,
                    }
                )
            )


async def main() -> None:
    symbols = [item.strip().upper() for item in sys.argv[1:] if item.strip()]
    if not symbols:
        raise SystemExit("Pass at least one NSE trading symbol.")
    try:
        await audit(symbols)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
