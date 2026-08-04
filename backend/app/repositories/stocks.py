from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import Numeric, and_, case, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    AnalysisChartSnapshot,
    AnalysisSnapshot,
    Company,
    Instrument,
    FundamentalPeriod,
    FundamentalCoverageStatus,
    FundamentalSnapshot,
    TechnicalStatus,
    TrackedInstrument,
    TrackingOperationalState,
    UserWatchlistItem,
)


StockSort = Literal[
    "status",
    "market_cap_desc",
    "market_cap_asc",
    "day_change_desc",
    "day_change_asc",
    "watchlist_change_desc",
    "watchlist_change_asc",
]
StockAnalysisRecord = tuple[
    Company,
    Instrument,
    AnalysisSnapshot | None,
    Decimal | None,
    FundamentalCoverageStatus | None,
    bool,
    TrackingOperationalState | None,
    date | None,
    str | None,
]


@dataclass(frozen=True, slots=True)
class StockAnalysisPage:
    records: list[StockAnalysisRecord]
    count: int


@dataclass(frozen=True, slots=True)
class StockDetailRecord:
    company: Company
    instrument: Instrument
    analysis: AnalysisSnapshot
    fundamentals: FundamentalSnapshot | None
    periods: list[FundamentalPeriod]
    has_chart_data: bool


@dataclass(frozen=True, slots=True)
class StockChartRecord:
    company: Company
    instrument: Instrument
    analysis: AnalysisSnapshot
    charts: list[AnalysisChartSnapshot]


async def list_latest_stock_analyses(
    session: AsyncSession,
    *,
    user_id: int,
    is_admin: bool,
    page: int,
    page_size: int | None,
    search: str | None,
    sort: StockSort,
) -> StockAnalysisPage:
    ranked_snapshots = (
        select(
            AnalysisSnapshot.id.label("snapshot_id"),
            AnalysisSnapshot.instrument_id.label("instrument_id"),
            func.row_number()
            .over(
                partition_by=AnalysisSnapshot.instrument_id,
                order_by=(
                    AnalysisSnapshot.analysis_date.desc(),
                    AnalysisSnapshot.generated_at.desc(),
                    AnalysisSnapshot.id.desc(),
                ),
            )
            .label("snapshot_rank"),
        )
        .subquery()
    )
    status_order = case(
        (AnalysisSnapshot.technical_status == TechnicalStatus.BREAKOUT, 0),
        (
            AnalysisSnapshot.technical_status
            == TechnicalStatus.EARLY_RECOVERY_BREAKOUT,
            1,
        ),
        (
            AnalysisSnapshot.technical_status
            == TechnicalStatus.WEAK_BREAKOUT,
            2,
        ),
        (AnalysisSnapshot.technical_status == TechnicalStatus.RETEST, 3),
        (
            AnalysisSnapshot.technical_status
            == TechnicalStatus.BREAKOUT_HOLDING,
            4,
        ),
        (AnalysisSnapshot.technical_status == TechnicalStatus.CONSOLIDATING, 5),
        # Historical states remain sortable while old snapshots are readable.
        (AnalysisSnapshot.technical_status == TechnicalStatus.READY, 6),
        (AnalysisSnapshot.technical_status == TechnicalStatus.FORMING, 7),
        (
            AnalysisSnapshot.technical_status
            == TechnicalStatus.SETUP_FOUND,
            8,
        ),
        (
            AnalysisSnapshot.technical_status
            == TechnicalStatus.FAILED_BREAKOUT,
            9,
        ),
        (AnalysisSnapshot.technical_status == TechnicalStatus.NO_SETUP, 10),
        else_=11,
    )
    operational_failure_order = case(
        (
            TrackedInstrument.operational_state
            == TrackingOperationalState.ANALYSIS_FAILED,
            1,
        ),
        (AnalysisSnapshot.id.is_(None), 2),
        else_=0,
    )
    market_cap = (
        select(
            cast(
                FundamentalSnapshot.metrics["profile"][
                    "sector_market_cap_inr_crore"
                ].astext,
                Numeric,
            )
        )
        .where(FundamentalSnapshot.instrument_id == Instrument.id)
        .order_by(
            FundamentalSnapshot.as_of_date.desc(),
            FundamentalSnapshot.source_fetched_at.desc(),
            FundamentalSnapshot.id.desc(),
        )
        .limit(1)
        .correlate(Instrument)
        .scalar_subquery()
    )
    fundamental_coverage = (
        select(FundamentalSnapshot.coverage)
        .where(FundamentalSnapshot.instrument_id == Instrument.id)
        .order_by(
            FundamentalSnapshot.as_of_date.desc(),
            FundamentalSnapshot.source_fetched_at.desc(),
            FundamentalSnapshot.id.desc(),
        )
        .limit(1)
        .correlate(Instrument)
        .scalar_subquery()
    )
    day_change = (
        (AnalysisSnapshot.close_price / AnalysisSnapshot.previous_close_price)
        - 1
    ) * 100
    baseline_membership = aliased(UserWatchlistItem)
    baseline_close = (
        select(baseline_membership.baseline_close_price)
        .where(
            baseline_membership.user_id == user_id,
            baseline_membership.instrument_id == Instrument.id,
            baseline_membership.is_active.is_(True),
        )
        .limit(1)
        .correlate(Instrument)
        .scalar_subquery()
    )
    watchlist_change = (
        (AnalysisSnapshot.close_price / baseline_close) - 1
    ) * 100
    has_chart_data = (
        select(AnalysisChartSnapshot.analysis_snapshot_id)
        .where(
            AnalysisChartSnapshot.analysis_snapshot_id
            == AnalysisSnapshot.id
        )
        .exists()
    )
    statement = (
        select(
            Company,
            Instrument,
            AnalysisSnapshot,
            market_cap.label("market_cap_crore"),
            fundamental_coverage.label("latest_fundamental_coverage"),
            has_chart_data.label("has_chart_data"),
            TrackedInstrument.operational_state,
            TrackedInstrument.terminal_data_error_session,
            TrackedInstrument.terminal_data_error_code,
        )
        .join(Instrument, Instrument.company_id == Company.id)
        .outerjoin(
            TrackedInstrument,
            TrackedInstrument.instrument_id == Instrument.id,
        )
        .outerjoin(
            ranked_snapshots,
            and_(
                ranked_snapshots.c.instrument_id == Instrument.id,
                ranked_snapshots.c.snapshot_rank == 1,
            ),
        )
        .outerjoin(
            AnalysisSnapshot,
            AnalysisSnapshot.id == ranked_snapshots.c.snapshot_id,
        )
    )
    if is_admin:
        statement = statement.where(TrackedInstrument.is_active.is_(True))
    else:
        statement = statement.join(
            UserWatchlistItem,
            UserWatchlistItem.instrument_id == Instrument.id,
        ).where(
            UserWatchlistItem.user_id == user_id,
            UserWatchlistItem.is_active.is_(True),
            Instrument.is_preexisting_before_bulk_scan.is_(True),
        )

    normalized_search = " ".join((search or "").strip().split())
    if normalized_search:
        statement = statement.where(
            Company.name.icontains(normalized_search, autoescape=True)
            | Instrument.trading_symbol.icontains(
                normalized_search,
                autoescape=True,
            )
        )

    count = await session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    sort_order = {
        "status": (
            operational_failure_order.asc(),
            status_order.asc(),
        ),
        "market_cap_desc": (market_cap.desc().nullslast(),),
        "market_cap_asc": (market_cap.asc().nullslast(),),
        "day_change_desc": (day_change.desc().nullslast(),),
        "day_change_asc": (day_change.asc().nullslast(),),
        "watchlist_change_desc": (
            watchlist_change.desc().nullslast(),
        ),
        "watchlist_change_asc": (
            watchlist_change.asc().nullslast(),
        ),
    }[sort]
    statement = statement.order_by(
        *sort_order,
        Instrument.trading_symbol,
    )
    if page_size is not None:
        statement = statement.limit(page_size).offset(
            (page - 1) * page_size
        )
    result = await session.execute(statement)

    return StockAnalysisPage(
        records=[
            (
                company,
                instrument,
                snapshot,
                market_cap_crore,
                latest_fundamental_coverage,
                bool(chart_available),
                operational_state,
                terminal_data_error_session,
                terminal_data_error_code,
            )
            for (
                company,
                instrument,
                snapshot,
                market_cap_crore,
                latest_fundamental_coverage,
                chart_available,
                operational_state,
                terminal_data_error_session,
                terminal_data_error_code,
            ) in result.tuples()
        ],
        count=int(count or 0),
    )


async def get_stock_detail_record(
    session: AsyncSession,
    instrument_id: int,
    *,
    user_id: int,
    is_admin: bool,
) -> StockDetailRecord | None:
    identity_statement = select(Company, Instrument).join(
        Instrument,
        Instrument.company_id == Company.id,
    )
    if is_admin:
        identity_statement = identity_statement.join(
            TrackedInstrument,
            TrackedInstrument.instrument_id == Instrument.id,
        ).where(
            Instrument.id == instrument_id,
            TrackedInstrument.is_active.is_(True),
        )
    else:
        identity_statement = (
            identity_statement
            .join(
                UserWatchlistItem,
                UserWatchlistItem.instrument_id == Instrument.id,
            )
            .where(
                Instrument.id == instrument_id,
                UserWatchlistItem.user_id == user_id,
                UserWatchlistItem.is_active.is_(True),
                Instrument.is_preexisting_before_bulk_scan.is_(True),
            )
        )
    identity = (await session.execute(identity_statement)).one_or_none()
    if identity is None:
        return None

    analysis = await session.scalar(
        select(AnalysisSnapshot)
        .where(AnalysisSnapshot.instrument_id == instrument_id)
        .order_by(
            desc(AnalysisSnapshot.analysis_date),
            desc(AnalysisSnapshot.generated_at),
            desc(AnalysisSnapshot.id),
        )
        .limit(1)
    )
    if analysis is None:
        return None

    fundamentals = await session.scalar(
        select(FundamentalSnapshot)
        .where(FundamentalSnapshot.instrument_id == instrument_id)
        .order_by(
            desc(FundamentalSnapshot.as_of_date),
            desc(FundamentalSnapshot.source_fetched_at),
            desc(FundamentalSnapshot.id),
        )
        .limit(1)
    )
    company, instrument = identity
    periods = list(
        await session.scalars(
            select(FundamentalPeriod)
            .where(FundamentalPeriod.company_id == company.id)
            .order_by(
                desc(FundamentalPeriod.period_end),
                FundamentalPeriod.period_kind,
                FundamentalPeriod.statement_basis,
            )
        )
    )
    has_chart_data = await session.scalar(
        select(
            select(AnalysisChartSnapshot.analysis_snapshot_id)
            .where(
                AnalysisChartSnapshot.analysis_snapshot_id == analysis.id
            )
            .exists()
        )
    )
    return StockDetailRecord(
        company,
        instrument,
        analysis,
        fundamentals,
        periods,
        bool(has_chart_data),
    )


async def get_stock_chart_record(
    session: AsyncSession,
    instrument_id: int,
    *,
    user_id: int,
    is_admin: bool,
) -> StockChartRecord | None:
    detail = await get_stock_detail_record(
        session,
        instrument_id,
        user_id=user_id,
        is_admin=is_admin,
    )
    if detail is None:
        return None
    charts = list(
        (
            await session.scalars(
                select(AnalysisChartSnapshot)
                .where(
                    AnalysisChartSnapshot.analysis_snapshot_id
                    == detail.analysis.id
                )
                .order_by(AnalysisChartSnapshot.timeframe)
            )
        ).all()
    )
    if not charts:
        return None
    return StockChartRecord(
        detail.company,
        detail.instrument,
        detail.analysis,
        charts,
    )
