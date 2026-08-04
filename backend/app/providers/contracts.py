from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DailyCandle:
    trading_date: date
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    open_interest: int


@dataclass(frozen=True, slots=True)
class InstrumentCandidate:
    company_name: str
    exchange: str
    trading_symbol: str
    isin: str
    instrument_key: str


@dataclass(frozen=True, slots=True)
class ExchangeSession:
    session_date: date
    is_open: bool
    closes_at: datetime | None = None


class RequestRateLimiter(Protocol):
    async def acquire(
        self,
        *,
        bucket_key: str,
        minimum_interval_seconds: float,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class FundamentalProfile:
    description: str
    sector: str
    sector_market_cap_inr_crore: Decimal | None


@dataclass(frozen=True, slots=True)
class FundamentalRatio:
    name: str
    company_value: Decimal | None
    sector_value: Decimal | None


@dataclass(frozen=True, slots=True)
class FundamentalPeriodData:
    period_end: date
    period_kind: str
    statement_basis: str
    currency: str
    metrics: dict[str, Decimal]


@dataclass(frozen=True, slots=True)
class ShareholdingPoint:
    period_end: date
    percentage: Decimal


@dataclass(frozen=True, slots=True)
class FundamentalBundle:
    profile: FundamentalProfile | None
    ratios: tuple[FundamentalRatio, ...]
    periods: tuple[FundamentalPeriodData, ...]
    shareholding: dict[str, tuple[ShareholdingPoint, ...]]
    available_groups: frozenset[str]


class MarketDataProvider(Protocol):
    async def get_daily_candles(
        self,
        *,
        instrument_key: str,
        from_date: date,
        to_date: date,
    ) -> tuple[DailyCandle, ...]: ...


class InstrumentSearchProvider(Protocol):
    async def search_nse_equities(
        self,
        *,
        query: str,
        limit: int = 20,
    ) -> tuple[InstrumentCandidate, ...]: ...


class ExchangeCalendarProvider(Protocol):
    async def get_nse_session(self, session_date: date) -> ExchangeSession: ...


class AnalysisMarketDataProvider(
    MarketDataProvider,
    ExchangeCalendarProvider,
    Protocol,
):
    """Provider capabilities required to resolve and analyze EOD sessions."""

    async def get_intraday_daily_candles(
        self,
        *,
        instrument_key: str,
    ) -> tuple[DailyCandle, ...]: ...


class FundamentalDataProvider(Protocol):
    async def get_fundamentals(self, *, isin: str) -> FundamentalBundle: ...
