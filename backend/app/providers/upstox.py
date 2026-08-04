import asyncio
from calendar import monthrange
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import quote

import httpx2 as httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel, SecretStr, ValidationError, model_validator

from app.providers.contracts import (
    DailyCandle,
    ExchangeSession,
    RequestRateLimiter,
    FundamentalBundle,
    FundamentalPeriodData,
    FundamentalProfile,
    FundamentalRatio,
    InstrumentCandidate,
    ShareholdingPoint,
)
from app.providers.errors import ProviderError

UPSTOX_API_BASE_URL = "https://api.upstox.com"

PositivePrice = Annotated[Decimal, Field(gt=0)]
NonNegativeInteger = Annotated[int, Field(ge=0)]


class _CandleRow(
    RootModel[
        tuple[
            datetime,
            PositivePrice,
            PositivePrice,
            PositivePrice,
            PositivePrice,
            NonNegativeInteger,
            NonNegativeInteger,
        ]
    ]
):
    @model_validator(mode="after")
    def validate_market_invariants(self) -> "_CandleRow":
        timestamp, open_price, high, low, close, _, _ = self.root
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Candle timestamp must include a timezone offset.")
        if high < max(open_price, low, close):
            raise ValueError("Candle high is below another price.")
        if low > min(open_price, high, close):
            raise ValueError("Candle low is above another price.")
        return self


class _HistoricalData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candles: tuple[_CandleRow, ...]


class _HistoricalResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: _HistoricalData


class _InstrumentItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=255)
    segment: Literal["NSE_EQ"]
    exchange: Literal["NSE"]
    isin: str = Field(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    instrument_key: str = Field(min_length=1, max_length=128)
    trading_symbol: str = Field(min_length=1, max_length=64)


class _InstrumentSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: tuple[_InstrumentItem, ...]


class _OpenExchange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    exchange: str
    start_time: int
    end_time: int


class _HolidayItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: date
    closed_exchanges: tuple[str, ...] = ()
    open_exchanges: tuple[_OpenExchange, ...] = ()


class _HolidayResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: tuple[_HolidayItem, ...]


class _MarketCapValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: Decimal | None = None


class _CompanyProfileData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_profile: str = Field(min_length=1, max_length=10000)
    sector: str = Field(min_length=1, max_length=255)
    sector_market_cap_inr: _MarketCapValue | None = None


class _CompanyProfileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: _CompanyProfileData


class _RatioItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=64)
    company_value: str | None = None
    sector_value: str | None = None


class _RatioResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: tuple[_RatioItem, ...]


class _HistoryValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: Decimal
    period: str = Field(min_length=8, max_length=8)
    change: str | None = None


class _HistoryCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str = Field(min_length=1, max_length=64)
    history: tuple[_HistoryValue, ...]


class _IncomeStatementData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["consolidated", "standalone"]
    time_period: Literal["yearly", "quarterly"]
    units_in: Literal["crore"]
    income_statement: tuple[_HistoryCategory, ...]


class _IncomeStatementResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: _IncomeStatementData


class _BalanceHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_asset: Decimal
    total_liability: Decimal
    period: str = Field(min_length=8, max_length=8)


class _BalanceSheetData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["consolidated", "standalone"]
    time_period: Literal["yearly", "quarterly"]
    units_in: Literal["crore"]
    history: tuple[_BalanceHistory, ...]


class _BalanceSheetResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: _BalanceSheetData


class _CashFlowData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["consolidated", "standalone"]
    time_period: Literal["yearly", "quarterly"]
    units_in: Literal["crore"]
    cash_flow: tuple[_HistoryCategory, ...]


class _CashFlowResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: _CashFlowData


class _ShareholdingHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period: str = Field(min_length=8, max_length=8)
    value: Annotated[Decimal, Field(ge=0, le=100)]


class _ShareholdingCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str = Field(min_length=1, max_length=64)
    history: tuple[_ShareholdingHistory, ...]


class _ShareholdingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success"]
    data: tuple[_ShareholdingCategory, ...]


class UpstoxClient:
    """Small authenticated client for the Upstox APIs used by this project."""

    def __init__(
        self,
        *,
        access_token: SecretStr,
        timeout_seconds: float = 10.0,
        requests_per_second: float | None = None,
        request_rate_limiter: RequestRateLimiter | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        token = access_token.get_secret_value().strip()
        if not token:
            raise ValueError("An Upstox access token is required.")
        if requests_per_second is not None and not 0 < requests_per_second <= 50:
            raise ValueError(
                "requests_per_second must be greater than 0 and at most 50."
            )

        self._client = httpx.AsyncClient(
            base_url=UPSTOX_API_BASE_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )
        self._session_cache: dict[date, ExchangeSession] = {}
        self._intraday_daily_cache: dict[str, tuple[DailyCandle, ...]] = {}
        self._request_interval_seconds = (
            0.0 if requests_per_second is None else 1 / requests_per_second
        )
        self._request_rate_limiter = request_rate_limiter
        self._next_request_at_by_api: dict[str, float] = {}
        self._request_slot_locks: dict[str, asyncio.Lock] = {}

    async def __aenter__(self) -> "UpstoxClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_daily_candles(
        self,
        *,
        instrument_key: str,
        from_date: date,
        to_date: date,
    ) -> tuple[DailyCandle, ...]:
        if from_date > to_date:
            raise ValueError("from_date cannot be after to_date.")

        normalized_key = instrument_key.strip()
        if not normalized_key or len(normalized_key) > 100:
            raise ValueError("instrument_key must contain 1 to 100 characters.")

        encoded_key = quote(normalized_key, safe="")
        path = (
            f"/v3/historical-candle/{encoded_key}/days/1/"
            f"{to_date.isoformat()}/{from_date.isoformat()}"
        )
        payload = await self._get_json(path)

        try:
            response = _HistoricalResponse.model_validate(payload)
        except ValidationError as exc:
            raise ProviderError(
                code="UPSTOX_INVALID_RESPONSE",
                retryable=False,
            ) from exc

        candles = tuple(self._to_daily_candle(row) for row in response.data.candles)
        return tuple(sorted(candles, key=lambda candle: candle.trading_date))

    async def get_intraday_daily_candles(
        self,
        *,
        instrument_key: str,
    ) -> tuple[DailyCandle, ...]:
        normalized_key = instrument_key.strip()
        if not normalized_key or len(normalized_key) > 100:
            raise ValueError("instrument_key must contain 1 to 100 characters.")
        cached = self._intraday_daily_cache.get(normalized_key)
        if cached is not None:
            return cached

        encoded_key = quote(normalized_key, safe="")
        payload = await self._get_json(
            f"/v3/historical-candle/intraday/{encoded_key}/days/1"
        )
        try:
            response = _HistoricalResponse.model_validate(payload)
        except ValidationError as exc:
            raise ProviderError(
                code="UPSTOX_INVALID_RESPONSE",
                retryable=False,
            ) from exc

        candles = tuple(self._to_daily_candle(row) for row in response.data.candles)
        result = tuple(sorted(candles, key=lambda candle: candle.trading_date))
        self._intraday_daily_cache[normalized_key] = result
        return result

    async def search_nse_equities(
        self,
        *,
        query: str,
        limit: int = 20,
    ) -> tuple[InstrumentCandidate, ...]:
        normalized_query = " ".join(query.strip().split())
        if len(normalized_query) < 2 or len(normalized_query) > 50:
            raise ValueError("query must contain 2 to 50 characters.")
        if limit < 1 or limit > 30:
            raise ValueError("limit must be between 1 and 30.")

        payload = await self._get_json(
            "/v2/instruments/search",
            params={
                "query": normalized_query,
                "exchanges": "NSE",
                "segments": "EQ",
                "page_number": 1,
                "records": limit,
            },
        )
        try:
            response = _InstrumentSearchResponse.model_validate(payload)
        except ValidationError as exc:
            raise ProviderError(code="UPSTOX_INVALID_RESPONSE", retryable=False) from exc

        return tuple(
            InstrumentCandidate(
                company_name=item.name.strip(),
                exchange=item.exchange,
                trading_symbol=item.trading_symbol.strip().upper(),
                isin=item.isin,
                instrument_key=item.instrument_key.strip(),
            )
            for item in response.data
        )

    async def get_nse_session(self, session_date: date) -> ExchangeSession:
        cached = self._session_cache.get(session_date)
        if cached is not None:
            return cached

        payload = await self._get_json(f"/v2/market/holidays/{session_date.isoformat()}")
        try:
            response = _HolidayResponse.model_validate(payload)
        except ValidationError as exc:
            raise ProviderError(code="UPSTOX_INVALID_RESPONSE", retryable=False) from exc

        matching = next((item for item in response.data if item.date == session_date), None)
        if matching is None:
            result = ExchangeSession(
                session_date=session_date,
                is_open=session_date.weekday() < 5,
            )
        else:
            special = next(
                (item for item in matching.open_exchanges if item.exchange == "NSE"),
                None,
            )
            if special is not None:
                result = ExchangeSession(
                    session_date=session_date,
                    is_open=True,
                    closes_at=datetime.fromtimestamp(special.end_time / 1000, tz=UTC),
                )
            else:
                result = ExchangeSession(
                    session_date=session_date,
                    is_open="NSE" not in matching.closed_exchanges and session_date.weekday() < 5,
                )

        self._session_cache[session_date] = result
        return result

    async def get_fundamentals(self, *, isin: str) -> FundamentalBundle:
        normalized_isin = self._validated_isin(isin)
        encoded_isin = quote(normalized_isin, safe="")
        base_path = f"/v2/fundamentals/{encoded_isin}"

        try:
            profile = _CompanyProfileResponse.model_validate(
                await self._get_json(f"{base_path}/profile")
            )
            ratios = _RatioResponse.model_validate(
                await self._get_json(f"{base_path}/key-ratios")
            )
            income = _IncomeStatementResponse.model_validate(
                await self._get_json(
                    f"{base_path}/income-statement",
                    params={"type": "consolidated", "time_period": "yearly"},
                )
            )
            balance = _BalanceSheetResponse.model_validate(
                await self._get_json(
                    f"{base_path}/balance-sheet",
                    params={"type": "consolidated"},
                )
            )
            cash_flow = _CashFlowResponse.model_validate(
                await self._get_json(
                    f"{base_path}/cash-flow",
                    params={"type": "consolidated"},
                )
            )
            shareholding = _ShareholdingResponse.model_validate(
                await self._get_json(f"{base_path}/share-holdings")
            )
            return self._to_fundamental_bundle(
                profile=profile,
                ratios=ratios,
                income=income,
                balance=balance,
                cash_flow=cash_flow,
                shareholding=shareholding,
            )
        except (ValidationError, ValueError) as exc:
            raise ProviderError(code="UPSTOX_INVALID_RESPONSE", retryable=False) from exc

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, object] | None = None,
    ) -> object:
        if self._request_interval_seconds > 0:
            api_key = self._rate_limit_api_key(path)
            if self._request_rate_limiter is not None:
                await self._request_rate_limiter.acquire(
                    bucket_key=f"upstox:{api_key}",
                    minimum_interval_seconds=self._request_interval_seconds,
                )
            else:
                request_slot_lock = self._request_slot_locks.setdefault(
                    api_key,
                    asyncio.Lock(),
                )
                async with request_slot_lock:
                    loop = asyncio.get_running_loop()
                    wait_seconds = (
                        self._next_request_at_by_api.get(api_key, 0.0)
                        - loop.time()
                    )
                    if wait_seconds > 0:
                        await asyncio.sleep(wait_seconds)
                    self._next_request_at_by_api[api_key] = (
                        loop.time() + self._request_interval_seconds
                    )
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderError(code="UPSTOX_TIMEOUT", retryable=True) from exc
        except httpx.RequestError as exc:
            raise ProviderError(code="UPSTOX_UNAVAILABLE", retryable=True) from exc

        if response.status_code in {401, 403}:
            raise ProviderError(code="UPSTOX_AUTH_FAILED", retryable=False)
        if response.status_code == 429:
            raise ProviderError(code="UPSTOX_RATE_LIMITED", retryable=True)
        if response.status_code >= 500:
            raise ProviderError(code="UPSTOX_UNAVAILABLE", retryable=True)
        if response.is_error:
            raise ProviderError(code="UPSTOX_REQUEST_REJECTED", retryable=False)

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError(
                code="UPSTOX_INVALID_RESPONSE",
                retryable=False,
            ) from exc

    @staticmethod
    def _rate_limit_api_key(path: str) -> str:
        parts = [part for part in path.split("?", 1)[0].split("/") if part]
        if parts[:2] == ["v3", "historical-candle"]:
            if len(parts) > 2 and parts[2] == "intraday":
                return "v3/historical-candle/intraday"
            return "v3/historical-candle"
        if parts[:2] == ["v2", "fundamentals"] and len(parts) >= 4:
            return f"v2/fundamentals/{{isin}}/{parts[3]}"
        if parts[:3] == ["v2", "market", "holidays"]:
            return "v2/market/holidays"
        return "/".join(parts)

    @staticmethod
    def _to_daily_candle(row: _CandleRow) -> DailyCandle:
        timestamp, open_price, high, low, close, volume, open_interest = row.root
        return DailyCandle(
            trading_date=timestamp.date(),
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            open_interest=open_interest,
        )

    @staticmethod
    def _validated_isin(isin: str) -> str:
        normalized = isin.strip().upper()
        if len(normalized) != 12 or not normalized.isalnum():
            raise ValueError("isin must be a 12-character alphanumeric value.")
        return normalized

    @staticmethod
    def _period_end(label: str) -> date:
        parsed = datetime.strptime(label, "%b %Y")
        return date(parsed.year, parsed.month, monthrange(parsed.year, parsed.month)[1])

    @staticmethod
    def _ratio_value(value: str | None) -> Decimal | None:
        if value is None:
            return None
        normalized = value.strip().upper().replace(",", "")
        if normalized in {"", "-", "N/A", "NA", "NM", "NULL"}:
            return None
        if normalized.endswith("%"):
            normalized = normalized[:-1]
        return Decimal(normalized)

    @classmethod
    def _to_fundamental_bundle(
        cls,
        *,
        profile: _CompanyProfileResponse,
        ratios: _RatioResponse,
        income: _IncomeStatementResponse,
        balance: _BalanceSheetResponse,
        cash_flow: _CashFlowResponse,
        shareholding: _ShareholdingResponse,
    ) -> FundamentalBundle:
        period_metrics: dict[date, dict[str, Decimal]] = {}

        def merge_categories(prefix: str, categories: tuple[_HistoryCategory, ...]) -> None:
            for category in categories:
                key = f"{prefix}.{category.category.strip().lower()}"
                for point in category.history:
                    period_metrics.setdefault(cls._period_end(point.period), {})[key] = point.value

        merge_categories("income", income.data.income_statement)
        merge_categories("cash_flow", cash_flow.data.cash_flow)
        for point in balance.data.history:
            metrics = period_metrics.setdefault(cls._period_end(point.period), {})
            metrics["balance.total_assets"] = point.total_asset
            metrics["balance.total_liabilities"] = point.total_liability

        normalized_shareholding = {
            item.category.strip().lower(): tuple(
                ShareholdingPoint(
                    period_end=cls._period_end(point.period),
                    percentage=point.value,
                )
                for point in item.history
            )
            for item in shareholding.data
        }
        available_groups = {
            "profile",
            *( ["ratios"] if ratios.data else [] ),
            *( ["income"] if income.data.income_statement else [] ),
            *( ["balance_sheet"] if balance.data.history else [] ),
            *( ["cash_flow"] if cash_flow.data.cash_flow else [] ),
            *( ["shareholding"] if shareholding.data else [] ),
        }
        profile_data = profile.data
        return FundamentalBundle(
            profile=FundamentalProfile(
                description=profile_data.company_profile.strip(),
                sector=profile_data.sector.strip(),
                sector_market_cap_inr_crore=(
                    profile_data.sector_market_cap_inr.value
                    if profile_data.sector_market_cap_inr is not None
                    else None
                ),
            ),
            ratios=tuple(
                FundamentalRatio(
                    name=item.name.strip().upper(),
                    company_value=cls._ratio_value(item.company_value),
                    sector_value=cls._ratio_value(item.sector_value),
                )
                for item in ratios.data
            ),
            periods=tuple(
                FundamentalPeriodData(
                    period_end=period_end,
                    period_kind="YEARLY",
                    statement_basis="CONSOLIDATED",
                    currency="INR",
                    metrics=metrics,
                )
                for period_end, metrics in sorted(period_metrics.items(), reverse=True)
            ),
            shareholding=normalized_shareholding,
            available_groups=frozenset(available_groups),
        )
