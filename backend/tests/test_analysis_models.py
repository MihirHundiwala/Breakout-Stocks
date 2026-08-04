from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisChartSnapshot,
    AnalysisSnapshot,
    Company,
    FundamentalCoverageStatus,
    Instrument,
    TechnicalStatus,
)


def chart_candles(count: int = 20) -> list[dict[str, object]]:
    return [
        {
            "date": date(2026, 6, 1).isoformat(),
            "open": "1460.00",
            "high": "1480.00",
            "low": "1450.00",
            "close": "1472.00",
            "volume": 1000,
        }
        for _ in range(count)
    ]


def build_snapshot(
    instrument: Instrument,
    **overrides: object,
) -> AnalysisSnapshot:
    values: dict[str, object] = {
        "instrument": instrument,
        "analysis_date": date(2026, 7, 22),
        "technical_status": TechnicalStatus.SETUP_FOUND,
        "fundamental_coverage": FundamentalCoverageStatus.PARTIAL,
        "close_price": Decimal("1472.0000"),
        "previous_close_price": Decimal("1450.0000"),
        "pivot_price": None,
        "breakout_confirmed_on": None,
        "source": "FIXTURE",
        "source_fetched_at": datetime(
            2026,
            7,
            22,
            16,
            0,
            tzinfo=UTC,
        ),
        "algorithm_version": "fixture-v1",
        "candle_revision": "synthetic-v1",
    }
    values.update(overrides)
    return AnalysisSnapshot(**values)


@pytest.mark.anyio
async def test_valid_company_instrument_and_snapshot_are_persisted(
    db_session: AsyncSession,
) -> None:
    company = Company(name="Example Industries Limited")
    instrument = Instrument(
        company=company,
        exchange="NSE",
        trading_symbol="EXAMPLE",
    )
    snapshot = build_snapshot(instrument)

    db_session.add(snapshot)
    await db_session.flush()

    assert company.id is not None
    assert instrument.id is not None
    assert snapshot.id is not None
    assert instrument.company is company
    assert snapshot.instrument is instrument
    assert snapshot.close_price == Decimal("1472.0000")
    assert instrument.is_preexisting_before_bulk_scan is True


@pytest.mark.anyio
async def test_early_recovery_breakout_status_is_persisted(
    db_session: AsyncSession,
) -> None:
    instrument = Instrument(
        company=Company(name="Recovery Industries Limited"),
        exchange="NSE",
        trading_symbol="RECOVERY",
    )
    snapshot = build_snapshot(
        instrument,
        technical_status=TechnicalStatus.EARLY_RECOVERY_BREAKOUT,
        algorithm_version="technical-v8",
    )

    db_session.add(snapshot)
    await db_session.flush()

    assert snapshot.technical_status == TechnicalStatus.EARLY_RECOVERY_BREAKOUT


@pytest.mark.anyio
async def test_breakout_holding_status_is_persisted(
    db_session: AsyncSession,
) -> None:
    instrument = Instrument(
        company=Company(name="Holding Industries Limited"),
        exchange="NSE",
        trading_symbol="HOLDING",
    )
    snapshot = build_snapshot(
        instrument,
        technical_status=TechnicalStatus.BREAKOUT_HOLDING,
        algorithm_version="technical-v12",
    )

    db_session.add(snapshot)
    await db_session.flush()

    assert snapshot.technical_status == TechnicalStatus.BREAKOUT_HOLDING


@pytest.mark.anyio
async def test_bulk_scan_instrument_can_be_marked_as_not_preexisting(
    db_session: AsyncSession,
) -> None:
    instrument = Instrument(
        company=Company(name="Temporary Scan Company Limited"),
        exchange="NSE",
        trading_symbol="TEMPSCAN",
        is_preexisting_before_bulk_scan=False,
    )

    db_session.add(instrument)
    await db_session.flush()

    assert instrument.id is not None
    assert instrument.is_preexisting_before_bulk_scan is False


@pytest.mark.anyio
async def test_instrument_identity_is_unique_within_exchange(
    db_session: AsyncSession,
) -> None:
    company = Company(name="Example Industries Limited")
    db_session.add_all(
        [
            Instrument(
                company=company,
                exchange="NSE",
                trading_symbol="EXAMPLE",
            ),
            Instrument(
                company=company,
                exchange="NSE",
                trading_symbol="EXAMPLE",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_analysis_identity_is_idempotent(
    db_session: AsyncSession,
) -> None:
    company = Company(name="Example Industries Limited")
    instrument = Instrument(
        company=company,
        exchange="NSE",
        trading_symbol="EXAMPLE",
    )
    db_session.add_all(
        [
            build_snapshot(instrument),
            build_snapshot(instrument),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_binary_status_rejects_a_pivot_price(
    db_session: AsyncSession,
) -> None:
    company = Company(name="Example Industries Limited")
    instrument = Instrument(
        company=company,
        exchange="NSE",
        trading_symbol="EXAMPLE",
    )
    snapshot = build_snapshot(
        instrument,
        technical_status=TechnicalStatus.SETUP_FOUND,
        pivot_price=Decimal("1480.0000"),
    )
    db_session.add(snapshot)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_snapshot_rejects_a_non_positive_close(
    db_session: AsyncSession,
) -> None:
    company = Company(name="Example Industries Limited")
    instrument = Instrument(
        company=company,
        exchange="NSE",
        trading_symbol="EXAMPLE",
    )
    snapshot = build_snapshot(
        instrument,
        close_price=Decimal("0.0000"),
    )
    db_session.add(snapshot)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_analysis_snapshot_stores_daily_and_weekly_chart_evidence(
    db_session: AsyncSession,
) -> None:
    instrument = Instrument(
        company=Company(name="Chart Evidence Limited"),
        exchange="NSE",
        trading_symbol="CHART",
    )
    snapshot = build_snapshot(instrument)
    snapshot.chart_snapshots = [
        AnalysisChartSnapshot(
            timeframe="DAILY",
            period_count=20,
            window_start=date(2026, 6, 1),
            window_end=date(2026, 7, 22),
            resistance_price=Decimal("1480"),
            resistance_zone_lower=Decimal("1475"),
            resistance_zone_upper=Decimal("1485"),
            resistance_touch_dates=["2026-06-10", "2026-07-01"],
            candles=chart_candles(),
            schema_version="technical-chart-v2",
        ),
        AnalysisChartSnapshot(
            timeframe="WEEKLY",
            period_count=26,
            window_start=date(2026, 1, 23),
            window_end=date(2026, 7, 22),
            resistance_price=Decimal("1500"),
            resistance_zone_lower=Decimal("1490"),
            resistance_zone_upper=Decimal("1510"),
            resistance_touch_dates=["2026-02-20", "2026-06-12"],
            candles=chart_candles(26),
            schema_version="technical-chart-v2",
        ),
    ]

    db_session.add(snapshot)
    await db_session.flush()

    assert len(snapshot.chart_snapshots) == 2
    assert all(item.analysis_snapshot_id == snapshot.id for item in snapshot.chart_snapshots)
    assert {item.timeframe for item in snapshot.chart_snapshots} == {"DAILY", "WEEKLY"}


@pytest.mark.anyio
async def test_analysis_chart_rejects_too_few_candles(
    db_session: AsyncSession,
) -> None:
    instrument = Instrument(
        company=Company(name="Invalid Chart Limited"),
        exchange="NSE",
        trading_symbol="BADCHART",
    )
    snapshot = build_snapshot(instrument)
    snapshot.chart_snapshots = [AnalysisChartSnapshot(
        timeframe="DAILY",
        period_count=20,
        window_start=date(2026, 6, 1),
        window_end=date(2026, 7, 22),
        resistance_price=Decimal("1480"),
        resistance_zone_lower=Decimal("1475"),
        resistance_zone_upper=Decimal("1485"),
        resistance_touch_dates=[],
        candles=chart_candles(19),
        schema_version="technical-chart-v2",
    )]
    db_session.add(snapshot)

    with pytest.raises(IntegrityError):
        await db_session.flush()
