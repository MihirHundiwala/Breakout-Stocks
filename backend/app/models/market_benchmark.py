from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Identity,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.benchmark_daily_candle import BenchmarkDailyCandle


class MarketBenchmark(Base):
    __tablename__ = "market_benchmarks"
    __table_args__ = (
        UniqueConstraint(
            "code",
            name="uq_market_benchmarks_code",
        ),
        UniqueConstraint(
            "provider",
            "instrument_key",
            name="uq_market_benchmarks_provider_key",
        ),
        CheckConstraint(
            "code = upper(btrim(code)) AND code <> ''",
            name="ck_market_benchmarks_code",
        ),
        CheckConstraint(
            "name = btrim(name) AND name <> ''",
            name="ck_market_benchmarks_name",
        ),
        CheckConstraint(
            "provider = upper(btrim(provider)) AND provider <> ''",
            name="ck_market_benchmarks_provider",
        ),
        CheckConstraint(
            "instrument_key = btrim(instrument_key) AND instrument_key <> ''",
            name="ck_market_benchmarks_instrument_key",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    candles: Mapped[list["BenchmarkDailyCandle"]] = relationship(
        back_populates="benchmark",
    )
