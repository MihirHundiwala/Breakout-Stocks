from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FundamentalCoverageStatus,
    FundamentalPeriod,
    FundamentalPeriodKind,
    FundamentalSnapshot,
    StatementBasis,
)
from app.providers.contracts import FundamentalBundle


FUNDAMENTAL_SCHEMA_VERSION = "upstox-fundamentals-v1"
EXPECTED_FUNDAMENTAL_GROUPS = frozenset(
    {
        "profile",
        "ratios",
        "income",
        "balance_sheet",
        "cash_flow",
        "shareholding",
    }
)


@dataclass(frozen=True, slots=True)
class FundamentalPersistenceResult:
    snapshot: FundamentalSnapshot
    period_count: int


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _snapshot_metrics(bundle: FundamentalBundle) -> dict[str, object]:
    profile = None
    if bundle.profile is not None:
        profile = {
            "description": bundle.profile.description,
            "sector": bundle.profile.sector,
            "sector_market_cap_inr_crore": bundle.profile.sector_market_cap_inr_crore,
        }
    return _json_value(
        {
            "profile": profile,
            "ratios": {
                item.name: {
                    "company_value": item.company_value,
                    "sector_value": item.sector_value,
                }
                for item in bundle.ratios
            },
            "shareholding": {
                category: [
                    {
                        "period_end": point.period_end,
                        "percentage": point.percentage,
                    }
                    for point in points
                ]
                for category, points in bundle.shareholding.items()
            },
            "available_groups": sorted(bundle.available_groups),
        }
    )  # type: ignore[return-value]


def coverage_for(bundle: FundamentalBundle) -> tuple[FundamentalCoverageStatus, int]:
    available = len(bundle.available_groups & EXPECTED_FUNDAMENTAL_GROUPS)
    if available == 0:
        return FundamentalCoverageStatus.UNKNOWN, 0
    if available == len(EXPECTED_FUNDAMENTAL_GROUPS):
        return FundamentalCoverageStatus.COMPLETE, available
    return FundamentalCoverageStatus.PARTIAL, available


async def persist_fundamentals(
    session: AsyncSession,
    *,
    instrument_id: int,
    company_id: int,
    as_of_date: date,
    bundle: FundamentalBundle,
    source_fetched_at: datetime,
) -> FundamentalPersistenceResult:
    coverage, available_count = coverage_for(bundle)

    for period in bundle.periods:
        statement = insert(FundamentalPeriod).values(
            company_id=company_id,
            period_end=period.period_end,
            period_kind=FundamentalPeriodKind(period.period_kind),
            statement_basis=StatementBasis(period.statement_basis),
            currency=period.currency,
            metrics=_json_value(period.metrics),
            source="UPSTOX",
            source_fetched_at=source_fetched_at,
            schema_version=FUNDAMENTAL_SCHEMA_VERSION,
        )
        await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_fundamental_periods_identity",
                set_={
                    "currency": statement.excluded.currency,
                    "metrics": statement.excluded.metrics,
                    "source": statement.excluded.source,
                    "source_fetched_at": statement.excluded.source_fetched_at,
                },
            )
        )

    snapshot_statement = insert(FundamentalSnapshot).values(
        instrument_id=instrument_id,
        as_of_date=as_of_date,
        coverage=coverage,
        available_metric_count=available_count,
        expected_metric_count=len(EXPECTED_FUNDAMENTAL_GROUPS),
        metrics=_snapshot_metrics(bundle),
        source="UPSTOX",
        source_fetched_at=source_fetched_at,
        schema_version=FUNDAMENTAL_SCHEMA_VERSION,
    )
    await session.execute(
        snapshot_statement.on_conflict_do_update(
            constraint="uq_fundamental_snapshots_identity",
            set_={
                "coverage": snapshot_statement.excluded.coverage,
                "available_metric_count": snapshot_statement.excluded.available_metric_count,
                "expected_metric_count": snapshot_statement.excluded.expected_metric_count,
                "metrics": snapshot_statement.excluded.metrics,
                "source": snapshot_statement.excluded.source,
                "source_fetched_at": snapshot_statement.excluded.source_fetched_at,
            },
        )
    )
    snapshot = await session.scalar(
        select(FundamentalSnapshot).where(
            FundamentalSnapshot.instrument_id == instrument_id,
            FundamentalSnapshot.as_of_date == as_of_date,
            FundamentalSnapshot.schema_version == FUNDAMENTAL_SCHEMA_VERSION,
        )
    )
    if snapshot is None:
        raise RuntimeError("Persisted fundamental snapshot was not found.")
    return FundamentalPersistenceResult(snapshot=snapshot, period_count=len(bundle.periods))
