from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    false,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.app_user import AppUser
    from app.models.instrument import Instrument


class UserWatchlistItem(Base):
    __tablename__ = "user_watchlist_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "instrument_id",
            name="uq_user_watchlist_items_user_instrument",
        ),
        CheckConstraint(
            "(is_active AND deactivated_at IS NULL) OR "
            "(NOT is_active AND deactivated_at IS NOT NULL)",
            name="ck_user_watchlist_items_active_deactivated_at",
        ),
        CheckConstraint(
            "reactivated_at IS NULL OR reactivated_at >= created_at",
            name="ck_user_watchlist_items_reactivated_at",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_user_watchlist_items_updated_at",
        ),
        CheckConstraint(
            "baseline_close_price IS NULL OR baseline_close_price > 0",
            name="ck_user_watchlist_items_baseline_close_positive",
        ),
        Index(
            "ix_user_watchlist_items_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "ix_user_watchlist_items_active_instrument",
            "instrument_id",
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("app_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    instrument_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    baseline_session: Mapped[date] = mapped_column(Date, nullable=False)
    baseline_close_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
    )
    telegram_setup_alert_pending: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    user: Mapped["AppUser"] = relationship(back_populates="watchlist_items")
    instrument: Mapped["Instrument"] = relationship(
        back_populates="user_watchlist_items"
    )
