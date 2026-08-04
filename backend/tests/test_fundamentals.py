from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, FundamentalPeriod, FundamentalSnapshot, Instrument
from app.models.status import FundamentalCoverageStatus
from app.providers.contracts import (
    FundamentalBundle,
    FundamentalPeriodData,
    FundamentalProfile,
    FundamentalRatio,
    ShareholdingPoint,
)
from app.services.fundamentals import coverage_for, persist_fundamentals


def complete_bundle() -> FundamentalBundle:
    return FundamentalBundle(
        profile=FundamentalProfile(
            description="Synthetic business description.",
            sector="Industrials",
            sector_market_cap_inr_crore=Decimal("1500.5"),
        ),
        ratios=(FundamentalRatio("P/E", Decimal("18.2"), Decimal("20.1")),),
        periods=(
            FundamentalPeriodData(
                period_end=date(2025, 3, 31),
                period_kind="YEARLY",
                statement_basis="CONSOLIDATED",
                currency="INR",
                metrics={"income.revenue": Decimal("100.25")},
            ),
        ),
        shareholding={
            "promoters": (
                ShareholdingPoint(date(2025, 3, 31), Decimal("51.25")),
            )
        },
        available_groups=frozenset(
            {"profile", "ratios", "income", "balance_sheet", "cash_flow", "shareholding"}
        ),
    )


def test_coverage_never_treats_missing_groups_as_failed_checks() -> None:
    empty = FundamentalBundle(None, (), (), {}, frozenset())
    partial = FundamentalBundle(None, (), (), {}, frozenset({"ratios"}))

    assert coverage_for(empty) == (FundamentalCoverageStatus.UNKNOWN, 0)
    assert coverage_for(partial) == (FundamentalCoverageStatus.PARTIAL, 1)
    assert coverage_for(complete_bundle()) == (FundamentalCoverageStatus.COMPLETE, 6)


@pytest.mark.anyio
async def test_persistence_is_idempotent_and_serializes_decimals(
    db_session: AsyncSession,
) -> None:
    instrument = Instrument(
        company=Company(name="Synthetic Fundamentals Limited"),
        exchange="NSE",
        trading_symbol="SYNFUND",
    )
    db_session.add(instrument)
    await db_session.flush()
    fetched_at = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)

    first = await persist_fundamentals(
        db_session,
        instrument_id=instrument.id,
        company_id=instrument.company_id,
        as_of_date=date(2026, 7, 24),
        bundle=complete_bundle(),
        source_fetched_at=fetched_at,
    )
    repeated = await persist_fundamentals(
        db_session,
        instrument_id=instrument.id,
        company_id=instrument.company_id,
        as_of_date=date(2026, 7, 24),
        bundle=complete_bundle(),
        source_fetched_at=fetched_at,
    )
    await db_session.flush()

    assert first.snapshot.id == repeated.snapshot.id
    assert first.snapshot.coverage == FundamentalCoverageStatus.COMPLETE
    assert first.snapshot.available_metric_count == 6
    assert first.snapshot.metrics["ratios"]["P/E"]["company_value"] == "18.2"
    assert await db_session.scalar(select(func.count()).select_from(FundamentalSnapshot)) == 1
    assert await db_session.scalar(select(func.count()).select_from(FundamentalPeriod)) == 1
    period = await db_session.scalar(select(FundamentalPeriod))
    assert period is not None
    assert period.metrics["income.revenue"] == "100.25"
