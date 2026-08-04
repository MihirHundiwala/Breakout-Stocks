from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.analysis_snapshot import AnalysisSnapshot
    from app.models.company import Company
    from app.models.tracked_instrument import TrackedInstrument
    from app.models.user_watchlist_item import UserWatchlistItem


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "trading_symbol",
            name="uq_instruments_exchange_trading_symbol",
        ),
        CheckConstraint(
            (
                "exchange = btrim(exchange) "
                "AND exchange = upper(exchange) "
                "AND exchange <> ''"
            ),
            name="ck_instruments_exchange_normalized",
        ),
        CheckConstraint(
            (
                "trading_symbol = btrim(trading_symbol) "
                "AND trading_symbol = upper(trading_symbol) "
                "AND trading_symbol <> ''"
            ),
            name="ck_instruments_symbol_normalized",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    exchange: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    trading_symbol: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    is_preexisting_before_bulk_scan: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    company: Mapped["Company"] = relationship(
        back_populates="instruments",
    )
    analysis_snapshots: Mapped[list["AnalysisSnapshot"]] = relationship(
        back_populates="instrument",
    )
    tracked_instrument: Mapped["TrackedInstrument | None"] = relationship(
        back_populates="instrument",
        uselist=False,
    )
    user_watchlist_items: Mapped[list["UserWatchlistItem"]] = relationship(
        back_populates="instrument",
    )
