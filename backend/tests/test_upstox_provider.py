import asyncio
from datetime import date
from decimal import Decimal
from time import monotonic

import httpx2 as httpx
import pytest
from pydantic import SecretStr

from app.providers.errors import ProviderError
from app.providers.upstox import UpstoxClient


def _client_for(handler: httpx.AsyncBaseTransport) -> UpstoxClient:
    return UpstoxClient(
        access_token=SecretStr("provider-test-token"),
        transport=handler,
    )


@pytest.mark.anyio
async def test_configured_request_starts_are_paced() -> None:
    starts: list[float] = []

    async def handler(_request: httpx.Request) -> httpx.Response:
        starts.append(monotonic())
        return httpx.Response(200, json={"status": "success"})

    async with UpstoxClient(
        access_token=SecretStr("provider-test-token"),
        requests_per_second=50,
        transport=httpx.MockTransport(handler),
    ) as client:
        await asyncio.gather(
            client._get_json(
                "/v3/historical-candle/NSE_EQ%7CFIRST/days/1/2026-07-27"
            ),
            client._get_json(
                "/v3/historical-candle/NSE_EQ%7CSECOND/days/1/2026-07-27"
            ),
        )

    assert len(starts) == 2
    assert starts[1] - starts[0] >= 0.015


@pytest.mark.anyio
async def test_different_api_families_do_not_block_each_other() -> None:
    starts: list[float] = []

    async def handler(_request: httpx.Request) -> httpx.Response:
        starts.append(monotonic())
        return httpx.Response(200, json={"status": "success"})

    async with UpstoxClient(
        access_token=SecretStr("provider-test-token"),
        requests_per_second=20,
        transport=httpx.MockTransport(handler),
    ) as client:
        await asyncio.gather(
            client._get_json("/v2/fundamentals/INE002A01018/profile"),
            client._get_json("/v2/fundamentals/INE002A01018/key-ratios"),
        )

    assert len(starts) == 2
    assert abs(starts[1] - starts[0]) < 0.03


@pytest.mark.anyio
async def test_daily_candles_are_validated_mapped_and_sorted() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == (
            b"/v3/historical-candle/NSE_EQ%7CINE002A01018/days/1/"
            b"2026-07-24/2026-07-23"
        )
        assert request.headers["Authorization"] == "Bearer provider-test-token"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "candles": [
                        ["2026-07-24T00:00:00+05:30", 101, 106, 100, 105, 1200, 0],
                        ["2026-07-23T00:00:00+05:30", 99, 102, 98, 101, 900, 0],
                    ]
                },
            },
        )

    async with _client_for(httpx.MockTransport(handler)) as client:
        candles = await client.get_daily_candles(
            instrument_key="NSE_EQ|INE002A01018",
            from_date=date(2026, 7, 23),
            to_date=date(2026, 7, 24),
        )

    assert [candle.trading_date for candle in candles] == [
        date(2026, 7, 23),
        date(2026, 7, 24),
    ]
    assert candles[-1].close == Decimal("105")
    assert candles[-1].volume == 1200


@pytest.mark.anyio
async def test_intraday_daily_candle_uses_v3_current_day_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == (
            b"/v3/historical-candle/intraday/"
            b"NSE_EQ%7CINE002A01018/days/1"
        )
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "candles": [
                        [
                            "2026-07-27T00:00:00+05:30",
                            105,
                            108,
                            104,
                            107,
                            1400,
                            0,
                        ]
                    ]
                },
            },
        )

    async with _client_for(httpx.MockTransport(handler)) as client:
        candles = await client.get_intraday_daily_candles(
            instrument_key="NSE_EQ|INE002A01018",
        )

    assert [item.trading_date for item in candles] == [date(2026, 7, 27)]
    assert candles[0].close == Decimal("107")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "expected_code", "retryable"),
    [
        (401, "UPSTOX_AUTH_FAILED", False),
        (429, "UPSTOX_RATE_LIMITED", True),
        (503, "UPSTOX_UNAVAILABLE", True),
        (400, "UPSTOX_REQUEST_REJECTED", False),
    ],
)
async def test_http_failures_map_to_safe_errors(
    status_code: int,
    expected_code: str,
    retryable: bool,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"error": "provider body must not cross the boundary"},
        )

    async with _client_for(httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as captured:
            await client.get_daily_candles(
                instrument_key="NSE_EQ|INE002A01018",
                from_date=date(2026, 7, 23),
                to_date=date(2026, 7, 24),
            )

    assert captured.value.code == expected_code
    assert captured.value.retryable is retryable
    assert "provider body" not in str(captured.value)
    assert "provider-test-token" not in repr(captured.value)


@pytest.mark.anyio
async def test_invalid_candle_payload_is_rejected() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "candles": [
                        ["2026-07-24T00:00:00+05:30", 101, 100, 98, 105, 1200, 0]
                    ]
                },
            },
        )

    async with _client_for(httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as captured:
            await client.get_daily_candles(
                instrument_key="NSE_EQ|INE002A01018",
                from_date=date(2026, 7, 23),
                to_date=date(2026, 7, 24),
            )

    assert captured.value.code == "UPSTOX_INVALID_RESPONSE"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_timeout_is_retryable() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    async with _client_for(httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as captured:
            await client.get_daily_candles(
                instrument_key="NSE_EQ|INE002A01018",
                from_date=date(2026, 7, 23),
                to_date=date(2026, 7, 24),
            )

    assert captured.value.code == "UPSTOX_TIMEOUT"
    assert captured.value.retryable is True


@pytest.mark.anyio
async def test_invalid_date_range_does_not_call_provider() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        pytest.fail("Provider should not be called for invalid input.")

    async with _client_for(httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="from_date"):
            await client.get_daily_candles(
                instrument_key="NSE_EQ|INE002A01018",
                from_date=date(2026, 7, 24),
                to_date=date(2026, 7, 23),
            )


@pytest.mark.anyio
async def test_search_returns_only_validated_nse_equities() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/instruments/search"
        assert request.url.params["query"] == "Reliance Industries"
        assert request.url.params["exchanges"] == "NSE"
        assert request.url.params["segments"] == "EQ"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": [
                    {
                        "name": "RELIANCE INDUSTRIES LTD",
                        "segment": "NSE_EQ",
                        "exchange": "NSE",
                        "isin": "INE002A01018",
                        "instrument_key": "NSE_EQ|INE002A01018",
                        "trading_symbol": "RELIANCE",
                    }
                ],
            },
        )

    async with _client_for(httpx.MockTransport(handler)) as client:
        results = await client.search_nse_equities(query=" Reliance   Industries ")

    assert len(results) == 1
    assert results[0].isin == "INE002A01018"
    assert results[0].trading_symbol == "RELIANCE"


@pytest.mark.anyio
async def test_market_session_uses_special_timing_and_cache() -> None:
    call_count = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": [
                    {
                        "date": "2026-07-25",
                        "closed_exchanges": [],
                        "open_exchanges": [
                            {
                                "exchange": "NSE",
                                "start_time": 1784941200000,
                                "end_time": 1784948400000,
                            }
                        ],
                    }
                ],
            },
        )

    async with _client_for(httpx.MockTransport(handler)) as client:
        first = await client.get_nse_session(date(2026, 7, 25))
        second = await client.get_nse_session(date(2026, 7, 25))

    assert first.is_open is True
    assert first.closes_at is not None
    assert second == first
    assert call_count == 1


@pytest.mark.anyio
async def test_fundamentals_are_validated_and_normalized() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/profile"):
            payload = {
                "company_profile": "Example business description.",
                "sector": "Industrials",
                "sector_market_cap_inr": {"value": 1234.50, "unit": "crore"},
            }
        elif path.endswith("/key-ratios"):
            payload = [
                {"name": "P/E", "company_value": "20.15", "sector_value": "12.46"},
                {"name": "ROE", "company_value": "8.94%", "sector_value": "N/A"},
            ]
        elif path.endswith("/income-statement"):
            assert request.url.params["type"] == "consolidated"
            payload = {
                "type": "consolidated",
                "time_period": "yearly",
                "units_in": "crore",
                "income_statement": [
                    {"category": "revenue", "history": [{"period": "Mar 2025", "value": 100}]},
                    {"category": "net_profit", "history": [{"period": "Mar 2025", "value": 10}]},
                ],
            }
        elif path.endswith("/balance-sheet"):
            payload = {
                "type": "consolidated",
                "time_period": "yearly",
                "units_in": "crore",
                "history": [
                    {"period": "Mar 2025", "total_asset": 500, "total_liability": 200}
                ],
            }
        elif path.endswith("/cash-flow"):
            payload = {
                "type": "consolidated",
                "time_period": "yearly",
                "units_in": "crore",
                "cash_flow": [
                    {"category": "operating", "history": [{"period": "Mar 2025", "value": 15}]}
                ],
            }
        elif path.endswith("/share-holdings"):
            payload = [
                {"category": "promoters", "history": [{"period": "Mar 2025", "value": 51.25}]}
            ]
        else:
            pytest.fail(f"Unexpected fundamentals path: {path}")
        return httpx.Response(200, json={"status": "success", "data": payload})

    async with _client_for(httpx.MockTransport(handler)) as client:
        bundle = await client.get_fundamentals(isin="INE002A01018")

    assert bundle.profile is not None
    assert bundle.profile.sector == "Industrials"
    assert bundle.ratios[0].company_value == Decimal("20.15")
    assert bundle.ratios[1].company_value == Decimal("8.94")
    assert bundle.ratios[1].sector_value is None
    assert bundle.periods[0].period_end == date(2025, 3, 31)
    assert bundle.periods[0].metrics == {
        "income.revenue": Decimal("100"),
        "income.net_profit": Decimal("10"),
        "cash_flow.operating": Decimal("15"),
        "balance.total_assets": Decimal("500"),
        "balance.total_liabilities": Decimal("200"),
    }
    assert bundle.shareholding["promoters"][0].percentage == Decimal("51.25")
    assert bundle.available_groups == frozenset(
        {"profile", "ratios", "income", "balance_sheet", "cash_flow", "shareholding"}
    )


@pytest.mark.anyio
async def test_invalid_fundamental_percentage_is_rejected() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/profile"):
            payload: object = {"company_profile": "Description", "sector": "Sector"}
        elif request.url.path.endswith("/key-ratios"):
            payload = []
        elif request.url.path.endswith("/income-statement"):
            payload = {"type": "consolidated", "time_period": "yearly", "units_in": "crore", "income_statement": []}
        elif request.url.path.endswith("/balance-sheet"):
            payload = {"type": "consolidated", "time_period": "yearly", "units_in": "crore", "history": []}
        elif request.url.path.endswith("/cash-flow"):
            payload = {"type": "consolidated", "time_period": "yearly", "units_in": "crore", "cash_flow": []}
        else:
            payload = [{"category": "promoters", "history": [{"period": "Mar 2025", "value": 101}]}]
        return httpx.Response(200, json={"status": "success", "data": payload})

    async with _client_for(httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as captured:
            await client.get_fundamentals(isin="INE002A01018")

    assert captured.value.code == "UPSTOX_INVALID_RESPONSE"
