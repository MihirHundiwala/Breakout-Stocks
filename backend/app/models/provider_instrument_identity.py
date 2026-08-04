from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Identity, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderInstrumentIdentity(Base):
    __tablename__ = "provider_instrument_identities"
    __table_args__ = (
        CheckConstraint("provider = upper(btrim(provider)) AND provider <> ''", name="ck_provider_identities_provider"),
        CheckConstraint("instrument_key = btrim(instrument_key) AND instrument_key <> ''", name="ck_provider_identities_key"),
        CheckConstraint("isin = upper(btrim(isin)) AND isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'", name="ck_provider_identities_isin"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_provider_identities_dates"),
        Index("uq_provider_identities_active_instrument", "instrument_id", "provider", unique=True, postgresql_where=text("effective_to IS NULL")),
        Index("uq_provider_identities_active_key", "provider", "instrument_key", unique=True, postgresql_where=text("effective_to IS NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_key: Mapped[str] = mapped_column(String(128), nullable=False)
    isin: Mapped[str] = mapped_column(String(12), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
