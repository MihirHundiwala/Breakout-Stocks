from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Enum as SqlEnum, ForeignKey, Identity, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.status import FundamentalCoverageStatus, FundamentalPeriodKind, StatementBasis


class FundamentalSnapshot(Base):
    __tablename__ = "fundamental_snapshots"
    __table_args__ = (
        UniqueConstraint("instrument_id", "as_of_date", "schema_version", name="uq_fundamental_snapshots_identity"),
        CheckConstraint("available_metric_count >= 0 AND expected_metric_count > 0 AND available_metric_count <= expected_metric_count", name="ck_fundamental_snapshots_counts"),
        CheckConstraint("schema_version = btrim(schema_version) AND schema_version <> ''", name="ck_fundamental_snapshots_version"),
        CheckConstraint("source = upper(btrim(source)) AND source <> ''", name="ck_fundamental_snapshots_source"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    coverage: Mapped[FundamentalCoverageStatus] = mapped_column(SqlEnum(FundamentalCoverageStatus, name="ck_fundamental_snapshots_coverage", native_enum=False, create_constraint=True, validate_strings=True, length=16), nullable=False)
    available_metric_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_metric_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)


class FundamentalPeriod(Base):
    __tablename__ = "fundamental_periods"
    __table_args__ = (
        UniqueConstraint("company_id", "period_end", "period_kind", "statement_basis", "schema_version", name="uq_fundamental_periods_identity"),
        CheckConstraint("currency = upper(btrim(currency)) AND currency <> ''", name="ck_fundamental_periods_currency"),
        CheckConstraint("source = upper(btrim(source)) AND source <> ''", name="ck_fundamental_periods_source"),
        CheckConstraint("schema_version = btrim(schema_version) AND schema_version <> ''", name="ck_fundamental_periods_version"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_kind: Mapped[FundamentalPeriodKind] = mapped_column(SqlEnum(FundamentalPeriodKind, name="ck_fundamental_periods_kind", native_enum=False, create_constraint=True, validate_strings=True, length=16), nullable=False)
    statement_basis: Mapped[StatementBasis] = mapped_column(SqlEnum(StatementBasis, name="ck_fundamental_periods_basis", native_enum=False, create_constraint=True, validate_strings=True, length=16), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
