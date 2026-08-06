from io import BytesIO
from decimal import Decimal

from PIL import Image, ImageDraw, ImageFont

from app.models import AnalysisChartSnapshot, AnalysisSnapshot, TechnicalStatus


WIDTH = 1280
HEIGHT = 760
LEFT = 118
RIGHT = 48
TOP = 142
PRICE_BOTTOM = 588
VOLUME_TOP = 620
VOLUME_BOTTOM = 704


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _money(value: float) -> str:
    return f"INR {value:,.2f}"


def _short_date(value: str) -> str:
    year, month, day = value.split("-")
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{int(day):02d} {months[int(month) - 1]}"


def render_setup_chart_png(
    *,
    company_name: str,
    trading_symbol: str,
    snapshot: AnalysisSnapshot,
    chart: AnalysisChartSnapshot,
) -> bytes:
    candles = [
        {
            **item,
            "open_value": float(Decimal(str(item["open"]))),
            "high_value": float(Decimal(str(item["high"]))),
            "low_value": float(Decimal(str(item["low"]))),
            "close_value": float(Decimal(str(item["close"]))),
            "volume_value": int(item["volume"]),
        }
        for item in chart.candles
    ]
    if not candles:
        raise ValueError("Chart evidence must contain candles.")

    image = Image.new("RGB", (WIDTH, HEIGHT), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = _font(30, bold=True)
    subtitle_font = _font(19, bold=True)
    label_font = _font(17, bold=True)
    small_font = _font(15, bold=True)

    draw.text((40, 28), company_name, fill="#0f172a", font=title_font)
    chart_status = chart.technical_status or snapshot.technical_status
    status_label = (
        "Strong Breakout"
        if chart_status == TechnicalStatus.BREAKOUT
        else chart_status.value.replace("_", " ").title()
    )
    draw.text(
        (40, 72),
        f"{trading_symbol}  |  {chart.timeframe.title()} base  |  {chart.period_count} periods  |  {status_label}",
        fill="#475569",
        font=subtitle_font,
    )
    latest = candles[-1]
    previous_close = candles[-2]["close_value"] if len(candles) > 1 else None
    change = (
        ((latest["close_value"] / previous_close) - 1) * 100
        if previous_close and previous_close > 0
        else 0
    )
    change_color = "#047857" if change >= 0 else "#b91c1c"
    latest_label = f"Latest close {_money(latest['close_value'])}   {change:+.2f}%"
    latest_box = draw.textbbox((0, 0), latest_label, font=subtitle_font)
    draw.text(
        (WIDTH - 40 - (latest_box[2] - latest_box[0]), 32),
        latest_label,
        fill=change_color,
        font=subtitle_font,
    )

    plot_width = WIDTH - LEFT - RIGHT
    plot_height = PRICE_BOTTOM - TOP
    draw.rectangle((LEFT, TOP, WIDTH - RIGHT, PRICE_BOTTOM), fill="white")

    zone_lower = float(chart.resistance_zone_lower)
    zone_upper = float(chart.resistance_zone_upper)
    raw_minimum = min(zone_lower, *(item["low_value"] for item in candles))
    raw_maximum = max(zone_upper, *(item["high_value"] for item in candles))
    visible_range = max(raw_maximum - raw_minimum, raw_maximum * 0.01)
    minimum = raw_minimum - visible_range * 0.08
    maximum = raw_maximum + visible_range * 0.08

    def y(value: float) -> float:
        return TOP + ((maximum - value) / (maximum - minimum)) * plot_height

    step = plot_width / len(candles)

    def x(index: int) -> float:
        return LEFT + step * (index + 0.5)

    for index in range(5):
        tick = maximum - ((maximum - minimum) * index / 4)
        tick_y = y(tick)
        draw.line((LEFT, tick_y, WIDTH - RIGHT, tick_y), fill="#dbe4ef", width=2)
        label = f"{tick:,.2f}"
        bounds = draw.textbbox((0, 0), label, font=small_font)
        draw.text((LEFT - 12 - (bounds[2] - bounds[0]), tick_y - 9), label, fill="#475569", font=small_font)

    band_top = y(zone_upper)
    band_bottom = y(zone_lower)
    draw.rectangle((LEFT, band_top, WIDTH - RIGHT, max(band_top + 3, band_bottom)), fill="#fef3c7")
    threshold_y = y(zone_upper)
    for start in range(LEFT, WIDTH - RIGHT, 18):
        draw.line((start, threshold_y, min(start + 10, WIDTH - RIGHT), threshold_y), fill="#d97706", width=3)

    maximum_volume = max(1, *(item["volume_value"] for item in candles))
    touch_dates = set(chart.resistance_touch_dates)
    body_width = max(3, min(12, int(step * 0.62)))
    for index, candle in enumerate(candles):
        bullish = candle["close_value"] >= candle["open_value"]
        color = "#059669" if bullish else "#dc2626"
        candle_x = x(index)
        draw.line((candle_x, y(candle["high_value"]), candle_x, y(candle["low_value"])), fill=color, width=2)
        body_top = y(max(candle["open_value"], candle["close_value"]))
        body_bottom = y(min(candle["open_value"], candle["close_value"]))
        draw.rectangle(
            (candle_x - body_width / 2, body_top, candle_x + body_width / 2, max(body_top + 2, body_bottom)),
            fill=color,
        )
        if str(candle["date"]) in touch_dates:
            dot_y = y(candle["high_value"])
            draw.ellipse((candle_x - 6, dot_y - 6, candle_x + 6, dot_y + 6), fill="#f59e0b", outline="white", width=2)
        volume_height = (candle["volume_value"] / maximum_volume) * (VOLUME_BOTTOM - VOLUME_TOP)
        volume_color = "#86d7c2" if bullish else "#f3aaaa"
        draw.rectangle((candle_x - body_width / 2, VOLUME_BOTTOM - volume_height, candle_x + body_width / 2, VOLUME_BOTTOM), fill=volume_color)

    draw.line((LEFT, VOLUME_BOTTOM, WIDTH - RIGHT, VOLUME_BOTTOM), fill="#cbd5e1", width=2)
    draw.text((38, VOLUME_TOP), "Volume", fill="#475569", font=small_font)
    tick_indexes = sorted({0, (len(candles) - 1) // 3, ((len(candles) - 1) * 2) // 3, len(candles) - 1})
    for index in tick_indexes:
        label = _short_date(str(candles[index]["date"]))
        bounds = draw.textbbox((0, 0), label, font=small_font)
        draw.text((x(index) - (bounds[2] - bounds[0]) / 2, 720), label, fill="#475569", font=small_font)

    zone_label = f"Breakout zone: {_money(zone_lower)} - {_money(zone_upper)}"
    draw.text((LEFT, 108), zone_label, fill="#92400e", font=label_font)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
