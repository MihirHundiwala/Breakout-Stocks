from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from decimal import Decimal

import httpx2 as httpx
import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisChartSnapshot,
    AnalysisSnapshot,
    AppUser,
    Company,
    FundamentalCoverageStatus,
    Instrument,
    TechnicalStatus,
    TelegramConnection,
    TelegramNotification,
    TelegramNotificationStatus,
    UserRole,
    UserWatchlistItem,
)
from app.providers.telegram import TelegramClient, TelegramPhoto
from app.services.telegram_chart import HEIGHT, WIDTH, render_setup_chart_png
from app.services.telegram_delivery import (
    TelegramNotificationMaterial,
    _caption,
    _load_material,
)


@pytest.mark.anyio
async def test_client_uploads_chart_to_selected_user_chat() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = TelegramClient(
            bot_token="synthetic-token",
            client=http_client,
            minimum_interval_seconds=0,
        )
        await client.send_alert(
            chat_id="987654",
            caption="A setup changed",
            photos=[TelegramPhoto("chart.png", b"png-bytes")],
        )

    assert len(requests) == 1
    assert requests[0].url.path.endswith("/sendPhoto")
    body = requests[0].content
    assert b"987654" in body
    assert b"A setup changed" in body
    assert b"png-bytes" in body


@pytest.mark.anyio
async def test_client_sends_plain_text_morning_digest() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = TelegramClient(
            bot_token="synthetic-token",
            client=http_client,
            minimum_interval_seconds=0,
        )
        await client.send_message(
            chat_id="987654",
            text="Morning watchlist setups",
        )

    assert len(requests) == 1
    assert requests[0].url.path.endswith("/sendMessage")
    assert b"987654" in requests[0].content
    assert b"Morning+watchlist+setups" in requests[0].content


@pytest.mark.anyio
async def test_client_validates_start_updates() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [{
                    "update_id": 8,
                    "message": {
                        "text": "/start token",
                        "chat": {"id": 42, "type": "private"},
                        "from": {"id": 42, "username": "MarketWatcher"},
                    },
                }],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = TelegramClient(
            bot_token="synthetic-token",
            client=http_client,
            minimum_interval_seconds=0,
        )
        updates = await client.get_updates(offset=0)

    assert updates[0].update_id == 8
    assert updates[0].message is not None
    assert updates[0].message.sender is not None
    assert updates[0].message.sender.username == "MarketWatcher"


def test_watchlist_added_caption_is_not_described_as_status_change() -> None:
    generated_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    snapshot = AnalysisSnapshot(
        id=7,
        instrument_id=3,
        analysis_date=date(2026, 7, 31),
        technical_status=TechnicalStatus.RETEST,
        fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
        close_price=Decimal("105"),
        previous_close_price=Decimal("100"),
        source="UPSTOX",
        source_fetched_at=generated_at,
        algorithm_version="caption-test-v1",
        candle_revision="caption-test-r1",
        generated_at=generated_at,
    )
    material = TelegramNotificationMaterial(
        chat_id="42",
        company_name="Caption Industries Limited",
        trading_symbol="CAPTION",
        snapshot=snapshot,
        previous_snapshot=None,
        charts=[],
        event_kind="WATCHLIST_ADDED",
    )

    caption = _caption(material)

    assert "Added to watchlist - current setup: Retest" in caption
    assert "setup structure changed" not in caption


@pytest.mark.anyio
async def test_delivery_discards_alert_after_user_removes_stock(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    user = AppUser(
        username="removed-alert-user",
        role=UserRole.USER,
        password_hash="$argon2id$synthetic",
    )
    instrument = Instrument(
        company=Company(name="Removed Alert Industries Limited"),
        exchange="NSE",
        trading_symbol="REMOVEDALERT",
    )
    db_session.add_all((user, instrument))
    await db_session.flush()
    snapshot = AnalysisSnapshot(
        instrument_id=instrument.id,
        analysis_date=date(2026, 7, 31),
        technical_status=TechnicalStatus.BREAKOUT,
        fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
        close_price=Decimal("105"),
        previous_close_price=Decimal("100"),
        source="UPSTOX",
        source_fetched_at=now,
        algorithm_version="removed-alert-v1",
        candle_revision="removed-alert-r1",
        generated_at=now,
    )
    db_session.add_all((
        snapshot,
        TelegramConnection(
            user_id=user.id,
            telegram_chat_id="7001",
            telegram_username="removedalert",
            connected_at=now,
            updated_at=now,
        ),
        UserWatchlistItem(
            user_id=user.id,
            instrument_id=instrument.id,
            is_active=False,
            created_at=now - timedelta(minutes=2),
            updated_at=now,
            deactivated_at=now,
            baseline_session=date(2026, 7, 31),
        ),
    ))
    await db_session.flush()
    notification = TelegramNotification(
        user_id=user.id,
        analysis_snapshot_id=snapshot.id,
        event_kind="WATCHLIST_ADDED",
        status=TelegramNotificationStatus.PENDING,
        attempt_count=0,
        created_at=now,
        next_attempt_at=now,
    )
    db_session.add(notification)
    await db_session.flush()

    material = await _load_material(db_session, notification.id)

    assert material is None


def test_chart_renderer_creates_bounded_png_with_latest_candle() -> None:
    generated_at = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    snapshot = AnalysisSnapshot(
        id=2,
        instrument_id=1,
        analysis_date=date(2026, 7, 30),
        technical_status=TechnicalStatus.BREAKOUT,
        fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
        close_price=Decimal("118"),
        previous_close_price=Decimal("114"),
        source="UPSTOX",
        source_fetched_at=generated_at,
        algorithm_version="technical-v15",
        candle_revision="synthetic-revision",
        generated_at=generated_at,
    )
    candles = []
    start = date(2026, 7, 3)
    for index in range(20):
        close = Decimal("100") + index
        candles.append({
            "date": (start + timedelta(days=index)).isoformat(),
            "open": str(close - Decimal("1")),
            "high": str(close + Decimal("2")),
            "low": str(close - Decimal("2")),
            "close": str(close),
            "volume": 1000 + index * 50,
        })
    chart = AnalysisChartSnapshot(
        analysis_snapshot_id=2,
        timeframe="DAILY",
        period_count=20,
        window_start=start,
        window_end=start + timedelta(days=19),
        resistance_price=Decimal("116"),
        resistance_zone_lower=Decimal("115"),
        resistance_zone_upper=Decimal("117"),
        resistance_touch_dates=[candles[10]["date"]],
        candles=candles,
        schema_version="technical-chart-v3",
        generated_at=generated_at,
    )

    content = render_setup_chart_png(
        company_name="Synthetic Industries Limited",
        trading_symbol="SYNTH",
        snapshot=snapshot,
        chart=chart,
    )

    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(content) < 10 * 1024 * 1024
    with Image.open(BytesIO(content)) as image:
        assert image.size == (WIDTH, HEIGHT)
