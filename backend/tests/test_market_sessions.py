from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.providers.contracts import DailyCandle, ExchangeSession
from app.services.market_sessions import (
    MarketSessionResolutionError,
    resolve_latest_available_nse_session,
    resolve_latest_completed_nse_session,
)


class FakeCalendar:
    def __init__(self, sessions: dict[date, ExchangeSession]) -> None:
        self.sessions = sessions
        self.requested: list[date] = []

    async def get_nse_session(self, session_date: date) -> ExchangeSession:
        self.requested.append(session_date)
        return self.sessions.get(
            session_date,
            ExchangeSession(
                session_date=session_date,
                is_open=session_date.weekday() < 5,
            ),
        )


class FakeAvailableMarket(FakeCalendar):
    def __init__(
        self,
        available_dates: tuple[date, ...],
        intraday_dates: tuple[date, ...] = (),
    ) -> None:
        super().__init__({})
        self.available_dates = available_dates
        self.intraday_dates = intraday_dates
        self.candle_requests: list[tuple[str, date, date]] = []
        self.intraday_requests: list[str] = []

    def _candles(self, dates: tuple[date, ...]) -> tuple[DailyCandle, ...]:
        return tuple(
            DailyCandle(
                trading_date=item,
                timestamp=datetime.combine(
                    item,
                    datetime.min.time(),
                    tzinfo=UTC,
                ),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1000,
                open_interest=0,
            )
            for item in dates
        )

    async def get_daily_candles(self, **kwargs: object) -> tuple[DailyCandle, ...]:
        instrument_key = str(kwargs["instrument_key"])
        from_date = kwargs["from_date"]
        to_date = kwargs["to_date"]
        assert isinstance(from_date, date)
        assert isinstance(to_date, date)
        self.candle_requests.append((instrument_key, from_date, to_date))
        return self._candles(
            tuple(
                item
                for item in self.available_dates
                if from_date <= item <= to_date
            )
        )

    async def get_intraday_daily_candles(
        self,
        *,
        instrument_key: str,
    ) -> tuple[DailyCandle, ...]:
        self.intraday_requests.append(instrument_key)
        return self._candles(self.intraday_dates)


@pytest.mark.anyio
async def test_before_cutoff_uses_previous_completed_weekday() -> None:
    calendar = FakeCalendar({})

    result = await resolve_latest_completed_nse_session(
        calendar,
        now=datetime(2026, 7, 24, 9, 0, tzinfo=UTC),
    )

    assert result == date(2026, 7, 23)


@pytest.mark.anyio
async def test_after_cutoff_uses_current_weekday() -> None:
    calendar = FakeCalendar({})

    result = await resolve_latest_completed_nse_session(
        calendar,
        now=datetime(2026, 7, 24, 11, 0, tzinfo=UTC),
    )

    assert result == date(2026, 7, 24)


@pytest.mark.anyio
async def test_weekend_and_explicit_holiday_are_skipped() -> None:
    calendar = FakeCalendar(
        {
            date(2026, 7, 24): ExchangeSession(
                session_date=date(2026, 7, 24),
                is_open=False,
            )
        }
    )

    result = await resolve_latest_completed_nse_session(
        calendar,
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )

    assert result == date(2026, 7, 23)


@pytest.mark.anyio
async def test_special_weekend_session_is_respected() -> None:
    special_date = date(2026, 7, 25)
    calendar = FakeCalendar(
        {
            special_date: ExchangeSession(
                session_date=special_date,
                is_open=True,
                closes_at=datetime(2026, 7, 25, 8, 0, tzinfo=UTC),
            )
        }
    )

    result = await resolve_latest_completed_nse_session(
        calendar,
        now=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
    )

    assert result == special_date


@pytest.mark.anyio
async def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        await resolve_latest_completed_nse_session(
            FakeCalendar({}),
            now=datetime(2026, 7, 24, 12, 0),
        )


@pytest.mark.anyio
async def test_provider_available_session_falls_back_from_unpublished_day() -> None:
    market = FakeAvailableMarket(
        (date(2026, 7, 23), date(2026, 7, 24))
    )

    result = await resolve_latest_available_nse_session(
        market,
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        now=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
    )

    assert result == date(2026, 7, 24)
    assert market.candle_requests == [
        (
            "NSE_INDEX|Nifty 500",
            date(2026, 7, 13),
            date(2026, 7, 27),
        )
    ]
    assert market.intraday_requests == ["NSE_INDEX|Nifty 500"]


@pytest.mark.anyio
async def test_provider_available_session_uses_completed_intraday_daily_candle() -> None:
    market = FakeAvailableMarket(
        (date(2026, 7, 23), date(2026, 7, 24)),
        intraday_dates=(date(2026, 7, 27),),
    )

    result = await resolve_latest_available_nse_session(
        market,
        benchmark_instrument_key="NSE_INDEX|Nifty 500",
        now=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
    )

    assert result == date(2026, 7, 27)
    assert market.intraday_requests == ["NSE_INDEX|Nifty 500"]


@pytest.mark.anyio
async def test_provider_available_session_requires_a_recent_benchmark_candle() -> None:
    with pytest.raises(MarketSessionResolutionError, match="no published"):
        await resolve_latest_available_nse_session(
            FakeAvailableMarket(()),
            benchmark_instrument_key="NSE_INDEX|Nifty 500",
            now=datetime(2026, 7, 27, 17, 0, tzinfo=UTC),
        )
