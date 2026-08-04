from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, Identity, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.status import TelegramNotificationStatus


if TYPE_CHECKING:
    from app.models.analysis_snapshot import AnalysisSnapshot


class TelegramNotification(Base):
    """Durable outbox entry for one immutable analysis change."""

    __tablename__ = "telegram_notification_outbox"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "analysis_snapshot_id",
            name="uq_telegram_notification_user_analysis_snapshot",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_telegram_notification_attempt_count",
        ),
        CheckConstraint(
            "next_attempt_at >= created_at",
            name="ck_telegram_notification_next_attempt",
        ),
        CheckConstraint(
            "event_kind IN ('STATUS_CHANGED', 'SETUP_STRUCTURE_CHANGED', 'WATCHLIST_ADDED')",
            name="ck_telegram_notification_event_kind",
        ),
        CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND failed_at IS NULL) "
            "OR (status = 'RUNNING' AND started_at IS NOT NULL AND failed_at IS NULL) "
            "OR (status = 'FAILED' AND started_at IS NOT NULL AND failed_at IS NOT NULL)",
            name="ck_telegram_notification_status_timestamps",
        ),
        CheckConstraint(
            "(status = 'FAILED' AND error_code IS NOT NULL) OR "
            "(status <> 'FAILED' AND error_code IS NULL AND error_message IS NULL)",
            name="ck_telegram_notification_error_fields",
        ),
        Index(
            "ix_telegram_notification_pending",
            "status",
            "next_attempt_at",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_analysis_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_snapshots.id", ondelete="SET NULL"),
    )
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[TelegramNotificationStatus] = mapped_column(
        SqlEnum(
            TelegramNotificationStatus,
            name="ck_telegram_notification_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(512))

    analysis_snapshot: Mapped["AnalysisSnapshot"] = relationship(
        foreign_keys=[analysis_snapshot_id]
    )
    previous_analysis_snapshot: Mapped["AnalysisSnapshot | None"] = relationship(
        foreign_keys=[previous_analysis_snapshot_id]
    )
