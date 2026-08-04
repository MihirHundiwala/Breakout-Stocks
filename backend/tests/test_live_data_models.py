from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Company,
    DailyCandle,
    FundamentalCoverageStatus,
    FundamentalPeriod,
    FundamentalPeriodKind,
    FundamentalSnapshot,
    Instrument,
    ProviderInstrumentIdentity,
    StatementBasis,
)


FETCHED_AT = datetime(2026, 7, 25, 11, 0, tzinfo=UTC)


async def persisted_instrument(db_session: AsyncSession) -> Instrument:
    instrument = Instrument(
        company=Company(name="Example Industries Limited"),
        exchange="NSE",
        trading_symbol="EXAMPLE",
    )
    db_session.add(instrument)
    await db_session.flush()
    return instrument


@pytest.mark.anyio
async def test_live_research_rows_are_persisted(db_session: AsyncSession) -> None:
    instrument = await persisted_instrument(db_session)
    db_session.add_all(
        [
            ProviderInstrumentIdentity(
                instrument_id=instrument.id,
                provider="UPSTOX",
                instrument_key="NSE_EQ|INE002A01018",
                isin="INE002A01018",
                effective_from=date(2026, 7, 1),
                source_fetched_at=FETCHED_AT,
            ),
            DailyCandle(
                instrument_id=instrument.id,
                trading_date=date(2026, 7, 24),
                open_price=Decimal("100"),
                high_price=Decimal("106"),
                low_price=Decimal("99"),
                close_price=Decimal("105"),
                volume=1200,
                open_interest=0,
                source="UPSTOX",
                source_timestamp=FETCHED_AT,
                fetched_at=FETCHED_AT,
            ),
            FundamentalSnapshot(
                instrument_id=instrument.id,
                as_of_date=date(2026, 7, 24),
                coverage=FundamentalCoverageStatus.PARTIAL,
                available_metric_count=2,
                expected_metric_count=6,
                metrics={"pe": "18.2", "roe": "14.1"},
                source="UPSTOX",
                source_fetched_at=FETCHED_AT,
                schema_version="fundamentals-v1",
            ),
            FundamentalPeriod(
                company_id=instrument.company_id,
                period_end=date(2026, 3, 31),
                period_kind=FundamentalPeriodKind.YEARLY,
                statement_basis=StatementBasis.CONSOLIDATED,
                currency="INR",
                metrics={"revenue": "1000000", "net_profit": "120000"},
                source="UPSTOX",
                source_fetched_at=FETCHED_AT,
                schema_version="fundamentals-v1",
            ),
        ]
    )

    await db_session.flush()


@pytest.mark.anyio
async def test_daily_candle_identity_is_idempotent(db_session: AsyncSession) -> None:
    instrument = await persisted_instrument(db_session)
    values = {
        "instrument_id": instrument.id,
        "trading_date": date(2026, 7, 24),
        "open_price": Decimal("100"),
        "high_price": Decimal("106"),
        "low_price": Decimal("99"),
        "close_price": Decimal("105"),
        "volume": 1200,
        "open_interest": 0,
        "source": "UPSTOX",
        "source_timestamp": FETCHED_AT,
        "fetched_at": FETCHED_AT,
    }
    db_session.add_all([DailyCandle(**values), DailyCandle(**values)])

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_daily_candle_rejects_invalid_ohlc(db_session: AsyncSession) -> None:
    instrument = await persisted_instrument(db_session)
    db_session.add(
        DailyCandle(
            instrument_id=instrument.id,
            trading_date=date(2026, 7, 24),
            open_price=Decimal("100"),
            high_price=Decimal("101"),
            low_price=Decimal("99"),
            close_price=Decimal("105"),
            volume=1200,
            open_interest=0,
            source="UPSTOX",
            source_timestamp=FETCHED_AT,
            fetched_at=FETCHED_AT,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_only_one_active_provider_identity_is_allowed(db_session: AsyncSession) -> None:
    instrument = await persisted_instrument(db_session)
    db_session.add_all(
        [
            ProviderInstrumentIdentity(
                instrument_id=instrument.id,
                provider="UPSTOX",
                instrument_key="NSE_EQ|INE002A01018",
                isin="INE002A01018",
                effective_from=date(2026, 7, 1),
                source_fetched_at=FETCHED_AT,
            ),
            ProviderInstrumentIdentity(
                instrument_id=instrument.id,
                provider="UPSTOX",
                instrument_key="NSE_EQ|INE002A01019",
                isin="INE002A01019",
                effective_from=date(2026, 7, 2),
                source_fetched_at=FETCHED_AT,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_fundamental_coverage_counts_are_bounded(db_session: AsyncSession) -> None:
    instrument = await persisted_instrument(db_session)
    db_session.add(
        FundamentalSnapshot(
            instrument_id=instrument.id,
            as_of_date=date(2026, 7, 24),
            coverage=FundamentalCoverageStatus.PARTIAL,
            available_metric_count=7,
            expected_metric_count=6,
            metrics={},
            source="UPSTOX",
            source_fetched_at=FETCHED_AT,
            schema_version="fundamentals-v1",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()
