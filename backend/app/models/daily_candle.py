from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Identity, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyCandle(Base):
    __tablename__ = "daily_candles"
    __table_args__ = (
        UniqueConstraint("instrument_id", "trading_date", name="uq_daily_candles_instrument_date"),
        CheckConstraint("open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0", name="ck_daily_candles_prices_positive"),
        CheckConstraint("high_price >= greatest(open_price, low_price, close_price)", name="ck_daily_candles_high"),
        CheckConstraint("low_price <= least(open_price, high_price, close_price)", name="ck_daily_candles_low"),
        CheckConstraint("volume >= 0 AND open_interest >= 0", name="ck_daily_candles_activity_non_negative"),
        CheckConstraint("source = upper(btrim(source)) AND source <> ''", name="ck_daily_candles_source"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    open_interest: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
